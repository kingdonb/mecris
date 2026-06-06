use serde::{Deserialize, Serialize};
use spin_sdk::{
    http::{Request, Response, Method},
    http_component,
    pg::{Connection, ParameterValue, DbValue},
    variables,
};
use spin_cron_sdk::{cron_component, Metadata};
use sha2::{Sha256, Digest};
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
use jwt_simple::prelude::*;
use aes_gcm::{aead::{Aead, KeyInit}, Aes256Gcm, Nonce};
use chrono::{Timelike, TimeZone};

#[derive(Deserialize, Default)] struct NotificationPrefs { #[allow(dead_code)] sms_opted_in: Option<bool> }
fn internal_api_key_ok(cfg: &str, h: Option<&str>) -> bool { if cfg.is_empty() { true } else { h == Some(cfg) } }

fn db_to_i32(v: &DbValue) -> i32 { 
    match v { 
        DbValue::Int16(i) => *i as i32, 
        DbValue::Int32(i) => *i, 
        DbValue::Int64(i) => *i as i32, 
        DbValue::Str(s) => s.parse().unwrap_or(0),
        _ => 0 
    } 
}
fn db_to_f64(v: &DbValue) -> f64 { 
    match v { 
        DbValue::Floating32(f) => *f as f64, 
        DbValue::Floating64(f) => *f, 
        DbValue::Str(s) => s.parse().unwrap_or(0.0),
        _ => 0.0 
    } 
}
fn db_to_str(v: &DbValue) -> String { match v { DbValue::Str(s) => s.clone(), _ => String::new() } }
fn db_to_bool(v: &DbValue) -> bool { match v { DbValue::Boolean(b) => *b, _ => false } }

fn json_response<T: Serialize>(status: u16, data: &T) -> anyhow::Result<Response> {
    let body = serde_json::to_vec(data)?;
    
    Ok(Response::builder()
        .status(status)
        .header("content-type", "application/json")
        .header("access-control-allow-origin", "*")
        .body(body)
        .build())
}

fn text_response(status: u16, text: &str) -> anyhow::Result<Response> {
    Ok(Response::builder()
        .status(status)
        .header("access-control-allow-origin", "*")
        .body(text.as_bytes().to_vec())
        .build())
}

#[cron_component]
async fn handle_cron(_metadata: Metadata) -> anyhow::Result<()> {
    let db_url = match variables::get("db_url").or_else(|_| variables::get("neon_db_url")) {
        Ok(url) if !url.is_empty() => url,
        _ => return Ok(()),
    };
    let default_user_id = "c0a81a4b-115a-4eb6-bc2c-40908c58bf64";
    let _ = run_clozemaster_scraper(&db_url, default_user_id).await;
    Ok(())
}

#[http_component]
async fn handle_sync_service(req: Request) -> anyhow::Result<Response> {
    let mut path = req.path().to_string();
    let method = req.method().clone();
    
    // Fix for full URLs in path
    if path.starts_with("http") {
        if let Some(p) = path.split('/').nth(3) {
            path = format!("/{}", p);
        }
    }
    

    if method == Method::Options {
        return Ok(Response::builder()
            .status(204)
            .header("access-control-allow-origin", "*")
            .header("access-control-allow-methods", "GET, POST, PATCH, OPTIONS")
            .header("access-control-allow-headers", "authorization, content-type, x-internal-api-key")
            .build());
    }

    let resp = match (path.as_str(), method) {
        ("/walks", Method::Post) => handle_walks_post(req).await,
        ("/budget", Method::Get) => handle_budget_get(req).await,
        ("/languages", Method::Get) => handle_languages_get(req).await,
        ("/languages/multiplier", Method::Post) => handle_multiplier_post(req).await,
        ("/health", Method::Get) => handle_health_get(req).await,
        ("/heartbeat", Method::Post) => handle_heartbeat_post(req).await,
        ("/internal/cloud-sync", Method::Post) => handle_cloud_sync(req).await,
        ("/aggregate-status", Method::Get) => handle_aggregate_status_get(req).await,
        ("/profile", Method::Post) => handle_profile_post(req).await,
        ("/profile", Method::Get) => handle_profile_get(req).await,
        ("/internal/trigger-reminders", _) => {
            let cfg = variables::get("internal_api_key").unwrap_or_default();
            let key = req.header("x-internal-api-key").and_then(|v| std::str::from_utf8(v.as_bytes()).ok());
            if !internal_api_key_ok(&cfg, key) { text_response(401, "Unauthorized") } else { handle_trigger_reminders_post(req).await }
        },
        ("/internal/failover-sync", _) => {
            let cfg = variables::get("internal_api_key").unwrap_or_default();
            let key = req.header("x-internal-api-key").and_then(|v| std::str::from_utf8(v.as_bytes()).ok());
            if !internal_api_key_ok(&cfg, key) { text_response(401, "Unauthorized") } else { handle_failover_sync_post(req).await }
        },
        ("/internal/weather-heuristic", Method::Get) => handle_weather_heuristic_get(req).await,
        ("/internal/request-phone-verification", Method::Post) => handle_request_phone_verification_post(req).await,
        ("/internal/confirm-phone-verification", Method::Post) => handle_confirm_phone_verification_post(req).await,
        ("/internal/twilio-webhook", Method::Post) => handle_twilio_webhook_post(req).await,
        _ => text_response(404, "Not Found"),
    };

    match resp {
        Ok(r) => Ok(r),
        Err(e) => {
            println!("Error processing request {}: {:?}", path, e);
            text_response(500, &format!("Internal Server Error: {}", e))
        }
    }
}

async fn handle_aggregate_status_get(req: Request) -> anyhow::Result<Response> {
    let auth = req.header("authorization").or_else(|| req.header("Authorization")).and_then(|v| std::str::from_utf8(v.as_bytes()).ok());
    let uid = match extract_user_id(auth).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let full = req.uri().contains("full=true");
    let db = match variables::get("db_url").or_else(|_| variables::get("neon_db_url")) { Ok(v) if !v.is_empty() => v, _ => return Err(anyhow::anyhow!("DB URL")) };
     let conn = Connection::open(&db)?;
    let walk_rs = conn.query("SELECT COUNT(*) FROM walk_inferences WHERE (start_time::TIMESTAMPTZ AT TIME ZONE 'US/Eastern')::DATE = (CURRENT_TIMESTAMP AT TIME ZONE 'US/Eastern')::DATE AND CAST(step_count AS INTEGER) >= 2000 AND user_id = $1", &[ParameterValue::Str(uid.clone())])?;
    let walked = !walk_rs.rows.is_empty() && (db_to_i32(&walk_rs.rows[0][0]) > 0);
    let lang_rows = conn.query("SELECT language_name, current_reviews, tomorrow_reviews, pump_multiplier::FLOAT8, daily_completions FROM language_stats WHERE user_id = $1", &[ParameterValue::Str(uid.clone())])?;
    let user_rows = conn.query("SELECT vacation_mode_until::TEXT, phone_verified FROM users WHERE pocket_id_sub = $1", &[ParameterValue::Str(uid.clone())])?;
    let (vaca, phone) = if !user_rows.rows.is_empty() { (match &user_rows.rows[0][0] { DbValue::Str(s) if !s.is_empty() => Some(s.clone()), _ => None }, db_to_bool(&user_rows.rows[0][1])) } else { (None, false) };
    let mut total_goals = 1; let mut goals_met = if walked { 1 } else { 0 };
    let (mut arabic_met, mut greek_met) = (false, false);
    for r in &lang_rows.rows {
        let n = db_to_str(&r[0]);
        let (cur, tom, mult, done) = (db_to_i32(&r[1]), db_to_i32(&r[2]), db_to_f64(&r[3]), db_to_i32(&r[4]));
        let (_, _, met) = calculate_targets(cur, tom, mult, done);
        if n == "ARABIC" { total_goals += 1; arabic_met = met; if met { goals_met += 1; } }
        else if n == "GREEK" { total_goals += 1; greek_met = met; if met { goals_met += 1; } }
    }
    #[derive(Serialize)] struct Comp { walk: bool, arabic: bool, greek: bool }
    #[derive(Serialize)] struct Mod { role: String, status: String, last_seen: String }
    #[derive(Serialize)] struct AggResp { score: String, goals_met: i32, total_goals: i32, all_clear: bool, components: Comp, vacation_mode_until: Option<String>, phone_verified: bool, modalities: Option<Vec<Mod>> }
    let mut mods = None;
    if full {
        let p_rows = conn.query("SELECT role, heartbeat::TEXT, CAST(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - heartbeat)) / 60 AS BIGINT) AS mins FROM scheduler_election WHERE user_id = $1 OR user_id IS NULL ORDER BY heartbeat DESC", &[ParameterValue::Str(uid.clone())])?;
        let mut ms = Vec::new();
        for r in &p_rows.rows {
            let role = db_to_str(&r[0]);
            let display = match role.as_str() { "leader" => "MCP SERVER", "android_client" => "ANDROID", "akamai_functions" => "AKAMAI", "fermyon_cloud" => "FERMYON", _ => &role };
            let mins = match r[2] { DbValue::Int64(i) => i as u64, _ => 9999 };
            ms.push(Mod { role: display.to_string(), status: get_modality_status(&role, mins).to_string(), last_seen: db_to_str(&r[1]) });
        }
        mods = Some(ms);
    }
    json_response(200, &AggResp { score: format!("{}/{}", goals_met, total_goals), goals_met, total_goals, all_clear: vaca.is_some() || goals_met >= total_goals, components: Comp { walk: walked, arabic: arabic_met, greek: greek_met }, vacation_mode_until: vaca, phone_verified: phone, modalities: mods })
}

fn calculate_targets(cur: i32, tom: i32, mult: f64, done: i32) -> (i32, f64, bool) {
    let rate = if mult > 0.0 { mult } else { 1.0 };
    let target = if cur + tom > 0 { ((cur + tom) as f64 / rate).ceil() as i32 } else { 0 };
    (target, rate, done >= target)
}

async fn handle_profile_post(req: Request) -> anyhow::Result<Response> {
    let auth = req.header("authorization").or_else(|| req.header("Authorization")).and_then(|v| std::str::from_utf8(v.as_bytes()).ok());
    let uid = match extract_user_id(auth).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let body = req.body();
    #[derive(Deserialize)] struct ProfReq { phone_number: Option<String>, beeminder_user: Option<String>, latitude: Option<f64>, longitude: Option<f64>, vacation_mode: Option<bool>, autonomous_sync_enabled: Option<bool>, notification_prefs: Option<serde_json::Value> }
    let pr: ProfReq = serde_json::from_slice(body)?;
    let db = match variables::get("db_url").or_else(|_| variables::get("neon_db_url")) { Ok(v) if !v.is_empty() => v, _ => return Err(anyhow::anyhow!("DB URL")) };
     let conn = Connection::open(&db)?;
    if let Some(p) = &pr.phone_number { let enc = encrypt_token(p).await?; conn.execute("UPDATE users SET phone_number_encrypted = $1, phone_verified = FALSE WHERE pocket_id_sub = $2", &[ParameterValue::Str(enc), ParameterValue::Str(uid.clone())])?; }
    if let Some(bu) = &pr.beeminder_user { let enc = encrypt_token(bu).await?; conn.execute("UPDATE users SET beeminder_user_encrypted = $1 WHERE pocket_id_sub = $2", &[ParameterValue::Str(enc), ParameterValue::Str(uid.clone())])?; }
    if let Some(lat) = pr.latitude { conn.execute("UPDATE users SET location_lat = $1 WHERE pocket_id_sub = $2", &[ParameterValue::Floating64(lat), ParameterValue::Str(uid.clone())])?; }
    if let Some(lon) = pr.longitude { conn.execute("UPDATE users SET location_lon = $1 WHERE pocket_id_sub = $2", &[ParameterValue::Floating64(lon), ParameterValue::Str(uid.clone())])?; }
    if let Some(vac) = pr.vacation_mode { if !vac { conn.execute("UPDATE users SET vacation_mode_until = NULL WHERE pocket_id_sub = $1", &[ParameterValue::Str(uid.clone())])?; } else { let u = (chrono::Utc::now() + chrono::Duration::days(1)).to_rfc3339(); conn.execute("UPDATE users SET vacation_mode_until = $1::TIMESTAMPTZ WHERE pocket_id_sub = $2", &[ParameterValue::Str(u), ParameterValue::Str(uid.clone())])?; } }
    if let Some(sync) = pr.autonomous_sync_enabled { conn.execute("UPDATE users SET autonomous_sync_enabled = $1 WHERE pocket_id_sub = $2", &[ParameterValue::Boolean(sync), ParameterValue::Str(uid.clone())])?; }
    if let Some(pref) = &pr.notification_prefs { conn.execute("UPDATE users SET notification_prefs = $1::JSONB WHERE pocket_id_sub = $2", &[ParameterValue::Str(serde_json::to_string(pref)?), ParameterValue::Str(uid.clone())])?; }
    json_response(200, &StatusResponse { status: "success".to_string(), message: "Profile updated".to_string() })
}

async fn handle_profile_get(req: Request) -> anyhow::Result<Response> {
    let auth = req.header("authorization").or_else(|| req.header("Authorization")).and_then(|v| std::str::from_utf8(v.as_bytes()).ok());
    let uid = match extract_user_id(auth).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let db = match variables::get("db_url").or_else(|_| variables::get("neon_db_url")) { Ok(v) if !v.is_empty() => v, _ => return Err(anyhow::anyhow!("DB URL")) };
     let conn = Connection::open(&db)?;
     let rs = conn.query("SELECT phone_number_encrypted, beeminder_user_encrypted, location_lat, location_lon, vacation_mode_until::TEXT, autonomous_sync_enabled FROM users WHERE pocket_id_sub = $1", &[ParameterValue::Str(uid.clone())])?;
    if rs.rows.is_empty() { return Ok(text_response(404, "User not found")?); }
    #[derive(Serialize)] struct ProfResp { phone_number: Option<String>, beeminder_user: Option<String>, latitude: Option<f64>, longitude: Option<f64>, vacation_mode_until: Option<String>, autonomous_sync_enabled: bool }
    let r = &rs.rows[0];
    let p = match &r[0] { DbValue::Str(s) if !s.is_empty() => decrypt_token(&s).await.ok(), _ => None };
    let bu = match &r[1] { DbValue::Str(s) if !s.is_empty() => decrypt_token(&s).await.ok(), _ => None };
    json_response(200, &ProfResp { phone_number: p, beeminder_user: bu, latitude: match rs.rows[0][2] { DbValue::Floating64(f) => Some(f), _ => None }, longitude: match rs.rows[0][3] { DbValue::Floating64(f) => Some(f), _ => None }, vacation_mode_until: match &rs.rows[0][4] { DbValue::Str(s) if !s.is_empty() => Some(s.clone()), _ => None }, autonomous_sync_enabled: db_to_bool(&rs.rows[0][5]) })
}

async fn handle_cloud_sync(req: Request) -> anyhow::Result<Response> {
    let auth = req.header("authorization").or_else(|| req.header("Authorization")).and_then(|v| std::str::from_utf8(v.as_bytes()).ok());
    let uid = match extract_user_id(auth).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let db = match variables::get("db_url").or_else(|_| variables::get("neon_db_url")) { Ok(v) if !v.is_empty() => v, _ => return Err(anyhow::anyhow!("DB URL")) };
    let _ = run_clozemaster_scraper(&db, &uid).await;
    json_response(200, &StatusResponse { status: "success".to_string(), message: "Sync initiated".to_string() })
}

async fn handle_health_get(req: Request) -> anyhow::Result<Response> {
    let auth = req.header("authorization").or_else(|| req.header("Authorization")).and_then(|v| std::str::from_utf8(v.as_bytes()).ok());
    let uid = match extract_user_id(auth).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let db = match variables::get("db_url").or_else(|_| variables::get("neon_db_url")) { Ok(v) if !v.is_empty() => v, _ => return Err(anyhow::anyhow!("DB URL")) };
     let conn = Connection::open(&db)?;
    register_cloud_heartbeat(&conn, &uid).await;
    #[derive(Serialize)] struct HealthResp { status: String, home_server_active: bool, leader_pid: String, last_seen: String }
    let mut active = false; let mut pid = "none".to_string(); let mut last = "never".to_string();
     let rs = conn.query("SELECT (heartbeat > CURRENT_TIMESTAMP - INTERVAL '90 seconds') as is_fresh, heartbeat::TEXT, process_id FROM scheduler_election WHERE user_id = $1 AND role = 'leader'", &[ParameterValue::Str(uid)])?;
    if !rs.rows.is_empty() { active = match rs.rows[0][0] { DbValue::Boolean(b) => b, _ => false }; last = db_to_str(&rs.rows[0][1]); pid = db_to_str(&rs.rows[0][2]); }
    json_response(200, &HealthResp { status: "ok".to_string(), home_server_active: active, leader_pid: pid, last_seen: last })
}

async fn handle_heartbeat_post(req: Request) -> anyhow::Result<Response> {
    let auth = req.header("authorization").or_else(|| req.header("Authorization")).and_then(|v| std::str::from_utf8(v.as_bytes()).ok());
    let uid = match extract_user_id(auth).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let body = req.body();
    let b: serde_json::Value = serde_json::from_slice(body)?;
    let pid = b.get("process_id").and_then(|v| v.as_str()).unwrap_or("unknown");
    let role = b.get("role").and_then(|v| v.as_str()).unwrap_or("leader");
    let db = match variables::get("db_url").or_else(|_| variables::get("neon_db_url")) { Ok(v) if !v.is_empty() => v, _ => return Err(anyhow::anyhow!("DB URL")) };
     let conn = Connection::open(&db)?;
    conn.execute("INSERT INTO scheduler_election (user_id, role, process_id, heartbeat) VALUES ($1, $2, $3, CURRENT_TIMESTAMP) ON CONFLICT (user_id, role) DO UPDATE SET heartbeat = EXCLUDED.heartbeat, process_id = EXCLUDED.process_id", &[ParameterValue::Str(uid), ParameterValue::Str(role.to_string()), ParameterValue::Str(pid.to_string())])?;
    json_response(200, &StatusResponse { status: "success".to_string(), message: "Heartbeat received".to_string() })
}

async fn handle_multiplier_post(req: Request) -> anyhow::Result<Response> {
    let auth = req.header("authorization").or_else(|| req.header("Authorization")).and_then(|v| std::str::from_utf8(v.as_bytes()).ok());
    let uid = match extract_user_id(auth).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let body = req.body();
    #[derive(Deserialize)] struct MultReq { name: String, multiplier: f64 }
    let data: MultReq = serde_json::from_slice(body)?;
    let db = match variables::get("db_url").or_else(|_| variables::get("neon_db_url")) { Ok(v) if !v.is_empty() => v, _ => return Err(anyhow::anyhow!("DB URL")) };
     let conn = Connection::open(&db)?;
    match conn.execute("UPDATE language_stats SET pump_multiplier = $1::FLOAT8::NUMERIC WHERE user_id = $2 AND language_name = $3", &[ParameterValue::Floating64(data.multiplier), ParameterValue::Str(uid), ParameterValue::Str(data.name.to_uppercase())]) {
        Ok(_) => Ok(text_response(200, "Multiplier updated")?),
        Err(e) => json_response(500, &StatusResponse { status: "error".to_string(), message: format!("DB: {}", e) })
    }
}

async fn handle_languages_get(req: Request) -> anyhow::Result<Response> {
    let auth = req.header("authorization").or_else(|| req.header("Authorization")).and_then(|v| std::str::from_utf8(v.as_bytes()).ok());
    let uid = match extract_user_id(auth).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let db = match variables::get("db_url").or_else(|_| variables::get("neon_db_url")) { Ok(v) if !v.is_empty() => v, _ => return Err(anyhow::anyhow!("DB URL")) };
     let conn = Connection::open(&db)?;
     let rs = conn.query("SELECT language_name, current_reviews, tomorrow_reviews, next_7_days_reviews, daily_rate::FLOAT8, safebuf, derail_risk, pump_multiplier::FLOAT8, beeminder_slug, daily_completions FROM language_stats WHERE user_id = $1 ORDER BY (beeminder_slug != '' AND beeminder_slug IS NOT NULL) DESC, language_name ASC", &[ParameterValue::Str(uid)])?;
    #[derive(Serialize)] struct LangStat { name: String, current: i32, tomorrow: i32, next_7_days: i32, daily_rate: f64, safebuf: i32, derail_risk: String, pump_multiplier: Option<f64>, daily_completions: i32, goal_met: bool, absolute_target: i32, has_goal: bool, target_flow_rate: Option<f64>, outstanding_debt: Option<i32> }
    let mut langs = Vec::new();
    for r in &rs.rows {
        let name = db_to_str(&r[0]);
        let cur = db_to_i32(&r[1]);
        let tom = db_to_i32(&r[2]);
        let n7 = db_to_i32(&r[3]);
        let rate = db_to_f64(&r[4]);
        let sb = db_to_i32(&r[5]);
        let risk = db_to_str(&r[6]);
        let mult = if let DbValue::Floating64(f) = r[7] { Some(f) } else { None };
        let slug = db_to_str(&r[8]);
        let done = db_to_i32(&r[9]);
        let (target, _, met) = calculate_targets(cur, tom, mult.unwrap_or(1.0), done);
        langs.push(LangStat { name, current: cur, tomorrow: tom, next_7_days: n7, daily_rate: rate, safebuf: sb, derail_risk: risk, pump_multiplier: mult, daily_completions: done, goal_met: met, absolute_target: target, has_goal: !slug.is_empty(), target_flow_rate: Some(rate), outstanding_debt: Some(cur) });
    }
    #[derive(Serialize)] struct LangResp { languages: Vec<LangStat> }
    json_response(200, &LangResp { languages: langs })
}

async fn handle_budget_get(req: Request) -> anyhow::Result<Response> {
    let auth = req.header("authorization").or_else(|| req.header("Authorization")).and_then(|v| std::str::from_utf8(v.as_bytes()).ok());
    let uid = match extract_user_id(auth).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let db = match variables::get("db_url").or_else(|_| variables::get("neon_db_url")) { Ok(v) if !v.is_empty() => v, _ => return Err(anyhow::anyhow!("DB URL")) };
     let conn = Connection::open(&db)?;
     let rs = conn.query("SELECT remaining_budget FROM budget_tracking WHERE user_id = $1 LIMIT 1", &[ParameterValue::Str(uid)])?;
    let budget = if rs.rows.is_empty() { 0.0 } else { db_to_f64(&rs.rows[0][0]) };
    #[derive(Serialize)] struct BudgetResp { remaining_budget: f64 }
    json_response(200, &BudgetResp { remaining_budget: budget })
}

async fn handle_walks_post(req: Request) -> anyhow::Result<Response> {
    let auth = req.header("authorization").or_else(|| req.header("Authorization")).and_then(|v| std::str::from_utf8(v.as_bytes()).ok());
    let uid = match extract_user_id(auth).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let body = req.body();
    #[derive(Deserialize)] struct WalkSum { start_time: String, end_time: String, step_count: i32, distance_meters: f64, distance_source: String, confidence_score: f64, gps_route_points: i32 }
    let walk: WalkSum = serde_json::from_slice(body)?;
    let db = match variables::get("db_url").or_else(|_| variables::get("neon_db_url")) { Ok(v) if !v.is_empty() => v, _ => return Err(anyhow::anyhow!("DB URL")) };
     let conn = Connection::open(&db)?;
    let _ = conn.execute("INSERT INTO users (pocket_id_sub, beeminder_token_encrypted, beeminder_goal) VALUES ($1, '', 'bike') ON CONFLICT DO NOTHING", &[ParameterValue::Str(uid.clone())]);
    let prev = conn.query("SELECT distance_meters FROM walk_inferences WHERE user_id = $1 AND start_time = $2", &[ParameterValue::Str(uid.clone()), ParameterValue::Str(walk.start_time.clone())])?;
    let prev_dist: f64 = if !prev.rows.is_empty() { match &prev.rows[0][0] { DbValue::Str(s) => s.parse().unwrap_or(0.0), _ => 0.0 } } else { 0.0 };
    let delta = walk.distance_meters - prev_dist;
    conn.execute("INSERT INTO walk_inferences (user_id, start_time, end_time, step_count, distance_meters, distance_source, confidence_score, gps_route_points) VALUES ($1, $2, $3, $4, $5, $6, $7, $8) ON CONFLICT (user_id, start_time) DO UPDATE SET end_time = EXCLUDED.end_time, step_count = EXCLUDED.step_count, distance_meters = EXCLUDED.distance_meters, distance_source = EXCLUDED.distance_source, confidence_score = EXCLUDED.confidence_score, gps_route_points = EXCLUDED.gps_route_points", &[ParameterValue::Str(uid.clone()), ParameterValue::Str(walk.start_time.clone()), ParameterValue::Str(walk.end_time.clone()), ParameterValue::Str(walk.step_count.to_string()), ParameterValue::Str(walk.distance_meters.to_string()), ParameterValue::Str(walk.distance_source.clone()), ParameterValue::Str(walk.confidence_score.to_string()), ParameterValue::Str(walk.gps_route_points.to_string())])?;
    let token = conn.query("SELECT beeminder_goal FROM users WHERE pocket_id_sub = $1", &[ParameterValue::Str(uid.clone())])?;
    if !token.rows.is_empty() && delta > 200.0 {
        let goal = match &token.rows[0][0] { DbValue::Str(s) if !s.is_empty() => s.clone(), _ => "bike".to_string() };
        let miles = ((walk.distance_meters / 1609.34) * 1000.0).round() / 1000.0;
        let requestid = format!("{}-{}-{}-{}", uid, goal, walk.start_time, walk.distance_meters);
        let _ = push_to_beeminder_idempotent(&uid, &goal, miles, "Synced via Spin (Cumulative)", &requestid, &conn).await;
    }
    json_response(201, &StatusResponse { status: "success".to_string(), message: "Walk ingested".to_string() })
}

async fn handle_trigger_reminders_post(_req: Request) -> anyhow::Result<Response> {
    let sid = variables::get("twilio_account_sid")?;
    let _tok = decrypt_token(&variables::get("twilio_auth_token_encrypted")?).await?;
    let from = variables::get("twilio_from_number")?;
    let db = match variables::get("db_url").or_else(|_| variables::get("neon_db_url")) { Ok(v) if !v.is_empty() => v, _ => return Err(anyhow::anyhow!("DB URL")) };
     let conn = Connection::open(&db)?;
     let rs = conn.query("SELECT pocket_id_sub, phone_number_encrypted, COALESCE(timezone, 'UTC'), COALESCE(notification_prefs::TEXT, '{}') FROM users WHERE phone_number_encrypted IS NOT NULL AND phone_number_encrypted != '' AND autonomous_sync_enabled = true", &[])?;
    let (mut sent, mut errors, now) = (0, 0, chrono::Utc::now());
    let (today, epoch) = (now.format("%Y-%m-%d").to_string(), now.timestamp() as u64);
    for r in &rs.rows {
        let (uid, ph_enc, tz, pref_j) = (db_to_str(&r[0]), db_to_str(&r[1]), db_to_str(&r[2]), db_to_str(&r[3]));
        let pref: NotificationPrefs = serde_json::from_str(&pref_j).unwrap_or_default();
        let s_rs = conn.query("SELECT step_count FROM walk_inferences WHERE user_id = $1 AND start_time >= $2 ORDER BY start_time ASC", &[ParameterValue::Str(uid.clone()), ParameterValue::Str(today.clone())])?;
        let steps = aggregate_step_count(&s_rs.rows);
        let m_rs = conn.query("SELECT sent_at::TEXT FROM message_log WHERE user_id = $1 AND type = 'walk_reminder' ORDER BY sent_at DESC LIMIT 1", &[ParameterValue::Str(uid.clone())])?;
        let ms = m_rs.rows.first().and_then(|mr| match &mr[0] { DbValue::Str(s) if !s.is_empty() => Some(s.as_str()), _ => None });
        let mins = ms.and_then(|s| chrono::DateTime::parse_from_rfc3339(s).or_else(|_| chrono::DateTime::parse_from_str(s, "%Y-%m-%d %H:%M:%S%.f%z")).ok().map(|dt| epoch.saturating_sub(dt.timestamp() as u64) / 60));
        if !should_dispatch(local_hour_from_timezone(&tz, &now), steps, mins, &pref) { continue; }
        let hb_rs = conn.query("SELECT EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - heartbeat)) / 60 FROM scheduler_election WHERE user_id = $1 AND role = 'android_client' ORDER BY heartbeat DESC LIMIT 1", &[ParameterValue::Str(uid.clone())])?;
        if hb_rs.rows.first().and_then(|hr| match hr[0] { DbValue::Floating64(f) => Some(f as u64), _ => None }).map_or(false, |m| m < 240) { continue; }
        let ph = decrypt_token(&ph_enc).await?;
        match send_twilio_sms(&sid, &_tok, &from, &ph, "Mecris: Time for a walk! Reply YES to log 1 mile.").await {
            Ok(_) => { let _ = conn.execute("INSERT INTO message_log (user_id, type, sent_at, compliance_status) VALUES ($1, 'walk_reminder', CURRENT_TIMESTAMP, 'sent')", &[ParameterValue::Str(uid.clone())]); sent += 1; }
            Err(_) => { errors += 1; }
        }
    }
    json_response(200, &format!("Sent {} reminders, {} errors", sent, errors))
}

async fn handle_failover_sync_post(_req: Request) -> anyhow::Result<Response> {
    let db = match variables::get("db_url").or_else(|_| variables::get("neon_db_url")) { Ok(v) if !v.is_empty() => v, _ => return Err(anyhow::anyhow!("DB URL")) };
     let conn = Connection::open(&db)?;
     let rs = conn.query("SELECT pocket_id_sub, EXTRACT(EPOCH FROM CURRENT_TIMESTAMP - COALESCE(last_autonomous_sync, '1970-01-01'::TIMESTAMPTZ))/60 FROM users WHERE autonomous_sync_enabled = true", &[])?;
    let mut success = 0;
    for r in &rs.rows {
        let uid = db_to_str(&r[0]);
        let mins = match r[1] { DbValue::Floating64(f) => f, _ => 0.0 };
        if mins > 1440.0 { if let Ok(_) = run_clozemaster_scraper(&db, &uid).await { success += 1; } }
    }
    json_response(200, &format!("Failover sync: {} success", success))
}

async fn handle_request_phone_verification_post(req: Request) -> anyhow::Result<Response> {
    let auth = req.header("authorization").or_else(|| req.header("Authorization")).and_then(|v| std::str::from_utf8(v.as_bytes()).ok());
    let uid = match extract_user_id(auth).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let body = req.body();
    #[derive(Deserialize)] struct Req { phone_number: String }
    let vr: Req = serde_json::from_slice(body)?;
    let db = match variables::get("db_url").or_else(|_| variables::get("neon_db_url")) { Ok(v) if !v.is_empty() => v, _ => return Err(anyhow::anyhow!("DB URL")) };
     let conn = Connection::open(&db)?;
    let mut rb = [0u8; 4]; getrandom::getrandom(&mut rb).map_err(|e| anyhow::anyhow!("getrandom: {}", e))?;
    let code = format!("{:06}", (u32::from_be_bytes(rb) % 1000000));
    let hash = hex::encode(Sha256::digest(code.as_bytes()));
    let exp = (chrono::Utc::now() + chrono::Duration::minutes(15)).to_rfc3339();
    conn.execute("INSERT INTO phone_verifications (user_id, code_hash, expires_at) VALUES ($1, $2, $3::TIMESTAMPTZ) ON CONFLICT (user_id) DO UPDATE SET code_hash = EXCLUDED.code_hash, expires_at = EXCLUDED.expires_at, attempts = 0", &[ParameterValue::Str(uid.clone()), ParameterValue::Str(hash), ParameterValue::Str(exp)])?;
    let sid = variables::get("twilio_account_sid")?;
    let auth = decrypt_token(&variables::get("twilio_auth_token_encrypted")?).await?;
    let from = variables::get("twilio_from_number")?;
    send_twilio_sms(&sid, &auth, &from, &vr.phone_number, &format!("Mecris code: {}", code)).await?;
    json_response(200, &"Verification code sent")
}

async fn handle_confirm_phone_verification_post(req: Request) -> anyhow::Result<Response> {
    let auth = req.header("authorization").or_else(|| req.header("Authorization")).and_then(|v| std::str::from_utf8(v.as_bytes()).ok());
    let uid = match extract_user_id(auth).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let body = req.body();
    #[derive(Deserialize)] struct Conf { code: String }
    let cr: Conf = serde_json::from_slice(body)?;
    let db = match variables::get("db_url").or_else(|_| variables::get("neon_db_url")) { Ok(v) if !v.is_empty() => v, _ => return Err(anyhow::anyhow!("DB URL")) };
     let conn = Connection::open(&db)?;
     let rs = conn.query("SELECT code_hash, CAST(EXTRACT(EPOCH FROM expires_at) AS BIGINT), attempts FROM phone_verifications WHERE user_id = $1", &[ParameterValue::Str(uid.clone())])?;
    if rs.rows.is_empty() { return Ok(text_response(400, "No request")?); }
    let db_hash = db_to_str(&rs.rows[0][0]);
    let exp = match rs.rows[0][1] { DbValue::Int64(i) => i as u64, _ => 0 };
    let att = db_to_i32(&rs.rows[0][2]);
    if att >= 5 { return Ok(text_response(429, "Too many attempts")?); }
    if chrono::Utc::now().timestamp() as u64 > exp { return Ok(text_response(400, "Expired")?); }
    if hex::encode(Sha256::digest(cr.code.as_bytes())) == db_hash {
        conn.execute("UPDATE users SET phone_verified = true WHERE pocket_id_sub = $1", &[ParameterValue::Str(uid.clone())])?;
        conn.execute("DELETE FROM phone_verifications WHERE user_id = $1", &[ParameterValue::Str(uid.clone())])?;
        json_response(200, &"Phone verified")
    } else {
        conn.execute("UPDATE phone_verifications SET attempts = attempts + 1 WHERE user_id = $1", &[ParameterValue::Str(uid.clone())])?;
        text_response(400, "Invalid code")
    }
}

async fn handle_twilio_webhook_post(req: Request) -> anyhow::Result<Response> {
    let _tok = decrypt_token(&variables::get("twilio_auth_token_encrypted")?).await?;
    let body = req.body();
    let body_str = std::str::from_utf8(body).unwrap_or("");
    let from_num = body_str.split('&').find_map(|p| { let mut i = p.splitn(2, '='); if i.next() == Some("From") { Some(urlencoding::decode(&i.next()?.replace('+', " ")).unwrap_or_default().into_owned()) } else { None } }).unwrap_or_default();
    if body_str.to_uppercase().contains("YES") {
        let db = match variables::get("db_url").or_else(|_| variables::get("neon_db_url")) { Ok(v) if !v.is_empty() => v, _ => return Err(anyhow::anyhow!("DB URL")) };
         let conn = Connection::open(&db)?;
         let rs = conn.query("SELECT pocket_id_sub, phone_number_encrypted, beeminder_goal FROM users WHERE phone_number_encrypted IS NOT NULL", &[])?;
        for r in &rs.rows {
            let (uid, ph_enc, goal) = (db_to_str(&r[0]), db_to_str(&r[1]), db_to_str(&r[2]));
            if let Ok(ph) = decrypt_token(&ph_enc).await {
                let clean = |s: &str| s.chars().filter(|c| c.is_digit(10)).collect::<String>();
                if !ph.is_empty() && clean(&ph) == clean(&from_num) {
                    let requestid = format!("{}-{}-{}-sms", uid, goal, chrono::Utc::now().format("%Y-%m-%d"));
                    let _ = push_to_beeminder_idempotent(&uid, &goal, 1.0, "Walk logged via SMS", &requestid, &conn).await;
                    let _ = conn.execute("INSERT INTO message_log (user_id, type, sent_at, compliance_status) VALUES ($1, 'walk_ack', CURRENT_TIMESTAMP, 'received')", &[ParameterValue::Str(uid)]);
                }
            }
        }
    }
    Ok(Response::builder().status(200).header("content-type", "text/xml").body(r#"<?xml version="1.0" encoding="UTF-8"?><Response></Response>"#.to_string().into_bytes()).build())
}

async fn run_clozemaster_scraper(db: &str, uid: &str) -> anyhow::Result<()> {
    let conn = Connection::open(db)?;
     let rs = conn.query("SELECT clozemaster_email_encrypted, clozemaster_password_encrypted FROM users WHERE pocket_id_sub = $1", &[ParameterValue::Str(uid.to_string())])?;
    if rs.rows.is_empty() { return Err(anyhow::anyhow!("User not found")); }
    let email = decrypt_token(&db_to_str(&rs.rows[0][0])).await?;
    let pass = decrypt_token(&db_to_str(&rs.rows[0][1])).await?;
    let ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36";
    let res: Response = spin_sdk::http::send::<_, Response>(Request::builder().method(Method::Get).uri("https://www.clozemaster.com/login").header("User-Agent", ua).build()).await?;
    let sess = res.header("set-cookie").and_then(|v| std::str::from_utf8(v.as_bytes()).ok()).unwrap_or("").split(';').next().unwrap_or("").to_string();
    let body = String::from_utf8(res.body().to_vec())?;
    let csrf = regex::Regex::new(r#"name="authenticity_token" value="([^"]*)""#)?.captures(&body).and_then(|cap| cap.get(1)).map(|m| m.as_str()).ok_or_else(|| anyhow::anyhow!("CSRF"))?;
    let login_body = format!("user%5Blogin%5D={}&user%5Bpassword%5D={}&authenticity_token={}&commit=Log+In", urlencoding::encode(&email), urlencoding::encode(&pass), urlencoding::encode(csrf));
    let res: Response = spin_sdk::http::send::<_, Response>(Request::builder().method(Method::Post).uri("https://www.clozemaster.com/login").header("content-type", "application/x-www-form-urlencoded").header("User-Agent", ua).header("Cookie", &sess).body(login_body.into_bytes()).build()).await?;
    let sess = res.header("set-cookie").and_then(|v| std::str::from_utf8(v.as_bytes()).ok()).unwrap_or(&sess).split(';').next().unwrap_or(&sess).to_string();
    let mut res: Response = spin_sdk::http::send::<_, Response>(Request::builder().method(Method::Get).uri("https://www.clozemaster.com/dashboard").header("User-Agent", ua).header("Cookie", &sess).build()).await?;
    if *res.status() == 302 { if let Some(loc) = res.header("location").and_then(|v| std::str::from_utf8(v.as_bytes()).ok()) { let url = if loc.starts_with('/') { format!("https://www.clozemaster.com{}", loc) } else { loc.to_string() }; res = spin_sdk::http::send::<_, Response>(Request::builder().method(Method::Get).uri(url).header("User-Agent", ua).header("Cookie", &sess).build()).await?; } }
    let body = String::from_utf8(res.body().to_vec())?;
    let props_escaped = regex::Regex::new(r#"data-react-props="([^"]*)""#)?.captures(&body).and_then(|cap| cap.get(1)).map(|m| m.as_str()).ok_or_else(|| anyhow::anyhow!("Props"))?;
    let fresh_csrf = regex::Regex::new(r#"<meta name="csrf-token" content="([^"]*)""#)?.captures(&body).and_then(|cap| cap.get(1)).map(|m| m.as_str()).unwrap_or(csrf);
    let props: serde_json::Value = serde_json::from_str(&html_escape::decode_html_entities(props_escaped))?;
    if let Some(pairings) = props.get("languagePairings").and_then(|l| l.as_array()) {
        for p in pairings {
            let id = p.get("id").and_then(|v| v.as_i64()).unwrap_or(0);
            let slug_name = p.get("slug").and_then(|v| v.as_str()).unwrap_or("UNKNOWN").to_string();
            let cur = p.get("numReadyForReview").and_then(|v| v.as_i64()).unwrap_or(0) as i32;
            let tot = p.get("score").and_then(|v| v.as_i64()).unwrap_or(0) as i32;
            let tod = p.get("numPointsToday").and_then(|v| v.as_i64()).unwrap_or(0) as i32;
            let (lang, beem) = match slug_name.as_str() { "ara-eng" => ("ARABIC", "reviewstack"), "ell-eng" => ("GREEK", ""), _ => (slug_name.as_str(), ""), };
            let (mut tom, mut n7) = (0, 0);
            if id > 0 {
                let api_url = format!("https://www.clozemaster.com/api/v1/lp/{}/more-stats", id);
                if let Ok(api_res) = spin_sdk::http::send::<_, Response>(Request::builder().method(Method::Get).uri(api_url).header("User-Agent", ua).header("Cookie", &sess).header("X-CSRF-Token", fresh_csrf).header("X-Requested-With", "XMLHttpRequest").build()).await {
                    let api_json: serde_json::Value = serde_json::from_str(&String::from_utf8(api_res.body().to_vec())?)?;
                    if let Some(f) = api_json.get("reviewForecast").and_then(|v| v.as_array()) { if !f.is_empty() {
                        let parse = |v: &serde_json::Value| v.get("count").and_then(|v| v.as_i64()).unwrap_or_else(|| v.as_i64().unwrap_or(0)) as i32;
                        tom = parse(&f[0]); n7 = f.iter().take(7).map(parse).sum();
                    } }
                }
            }
             let rs = conn.query("SELECT current_reviews, (beeminder_last_sync AT TIME ZONE 'UTC')::TEXT FROM language_stats WHERE user_id = $1 AND language_name = $2", &[ParameterValue::Str(uid.to_string()), ParameterValue::Str(lang.to_uppercase())])?;
            let (mut prev, mut lsync) = (-1, String::new());
            if !rs.rows.is_empty() { prev = db_to_i32(&rs.rows[0][0]); lsync = db_to_str(&rs.rows[0][1]); }
            let mut compl = tod; if lang == "ARABIC" { compl = (tod as f64 / 16.0) as i32; }
            conn.execute("INSERT INTO language_stats (user_id, language_name, current_reviews, tomorrow_reviews, next_7_days_reviews, beeminder_slug, daily_completions, last_points, total_points, last_updated) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, CURRENT_TIMESTAMP) ON CONFLICT (user_id, language_name) DO UPDATE SET current_reviews = EXCLUDED.current_reviews, tomorrow_reviews = EXCLUDED.tomorrow_reviews, next_7_days_reviews = EXCLUDED.next_7_days_reviews, beeminder_slug = COALESCE(NULLIF(EXCLUDED.beeminder_slug, ''), language_stats.beeminder_slug), daily_completions = EXCLUDED.daily_completions, last_points = EXCLUDED.last_points, total_points = EXCLUDED.total_points, last_updated = CURRENT_TIMESTAMP", &[ParameterValue::Str(uid.to_string()), ParameterValue::Str(lang.to_uppercase()), ParameterValue::Int32(cur), ParameterValue::Int32(tom), ParameterValue::Int32(n7), ParameterValue::Str(beem.to_string()), ParameterValue::Int32(compl), ParameterValue::Int32(tot), ParameterValue::Int32(tot)])?;
            if !beem.is_empty() {
                let now_ny = chrono::Utc::now().with_timezone(&chrono_tz::America::New_York);
                let today_ny = now_ny.format("%Y-%m-%d").to_string();
                let already_synced = if lsync.is_empty() { false } else { match chrono::NaiveDateTime::parse_from_str(lsync.split('.').next().unwrap_or(""), "%Y-%m-%d %H:%M:%S") { Ok(ndt) => chrono::Utc.from_utc_datetime(&ndt).with_timezone(&chrono_tz::America::New_York).format("%Y-%m-%d").to_string() == today_ny, Err(_) => false } };
                if cur != prev || !already_synced {
                    let comment = format!("Auto-synced from Clozemaster (Cloud) at {} | Tomorrow: {} | 7-day: {}", now_ny.format("%Y-%m-%d %H:%M"), tom, n7);
                    let rid = format!("{}-{}-{}-{}", uid, beem, today_ny, cur);
                    if let Ok(_) = push_to_beeminder_idempotent(uid, beem, cur as f64, &comment, &rid, &conn).await { conn.execute("UPDATE language_stats SET beeminder_last_sync = CURRENT_TIMESTAMP WHERE user_id = $1 AND language_name = $2", &[ParameterValue::Str(uid.to_string()), ParameterValue::Str(lang.to_uppercase())])?; }
                }
                if let Ok((mut sb, mut risk, rate)) = fetch_from_beeminder(uid, beem, &conn).await {
                    if cur == 0 && tom == 0 && n7 == 0 { sb = 999; risk = "SAFE".to_string(); }
                    conn.execute("UPDATE language_stats SET safebuf = $1, derail_risk = $2, daily_rate = $3::FLOAT8::NUMERIC WHERE user_id = $4 AND language_name = $5", &[ParameterValue::Int32(sb), ParameterValue::Str(risk), ParameterValue::Floating64(rate), ParameterValue::Str(uid.to_string()), ParameterValue::Str(lang.to_uppercase())])?;
                }
            }
        }
    }
    Ok(())
}

async fn fetch_from_beeminder(uid: &str, slug: &str, conn: &Connection) -> anyhow::Result<(i32, String, f64)> {
     let rs = conn.query("SELECT beeminder_token_encrypted, beeminder_user_encrypted FROM users WHERE pocket_id_sub = $1", &[ParameterValue::Str(uid.to_string())])?;
    if rs.rows.is_empty() { return Err(anyhow::anyhow!("User")); }
    let tok = decrypt_token(&db_to_str(&rs.rows[0][0])).await?;
    let user = if let DbValue::Str(s) = &rs.rows[0][1] { if !s.is_empty() { decrypt_token(s).await? } else { "me".to_string() } } else { "me".to_string() };
    let res: Response = spin_sdk::http::send::<_, Response>(Request::builder().method(Method::Get).uri(format!("https://www.beeminder.com/api/v1/users/{}/goals/{}.json?auth_token={}", user, slug, tok)).build()).await?;
    let data: serde_json::Value = serde_json::from_str(&String::from_utf8(res.body().to_vec())?)?;
    let sb = data.get("safebuf").and_then(|v| v.as_i64()).unwrap_or(0) as i32;
    let rate = data.get("rate").and_then(|v| v.as_f64()).unwrap_or(0.0);
    let risk = if sb <= 0 { "CRITICAL" } else if sb == 1 { "WARNING" } else if sb <= 3 { "CAUTION" } else { "SAFE" };
    Ok((sb, risk.to_string(), rate))
}

async fn push_to_beeminder_idempotent(uid: &str, slug: &str, val: f64, comment: &str, rid: &str, conn: &Connection) -> anyhow::Result<()> {
     let rs = conn.query("SELECT beeminder_token_encrypted, beeminder_user_encrypted FROM users WHERE pocket_id_sub = $1", &[ParameterValue::Str(uid.to_string())])?;
    if rs.rows.is_empty() { return Err(anyhow::anyhow!("User")); }
    let tok = decrypt_token(&db_to_str(&rs.rows[0][0])).await?;
    let user = if let DbValue::Str(s) = &rs.rows[0][1] { if !s.is_empty() { decrypt_token(s).await? } else { "me".to_string() } } else { "me".to_string() };
    let body = format!("auth_token={}&value={}&comment={}&requestid={}", tok, val, urlencoding::encode(comment), urlencoding::encode(rid));
    let res: Response = spin_sdk::http::send::<_, Response>(Request::builder().method(Method::Post).uri(format!("https://www.beeminder.com/api/v1/users/{}/goals/{}/datapoints.json", user, slug)).header("content-type", "application/x-www-form-urlencoded").body(body.into_bytes()).build()).await?;
    if *res.status() == 422 { return Ok(()); }
    if !(200..300).contains(res.status()) { return Err(anyhow::anyhow!("Push fail: {}", res.status())); }
    Ok(())
}

async fn send_twilio_sms(sid: &str, tok: &str, from: &str, to: &str, msg: &str) -> anyhow::Result<()> {
    let auth = base64::engine::general_purpose::STANDARD.encode(format!("{}:{}", sid, tok));
    let body = format!("From={}&To={}&Body={}", urlencoding::encode(from), urlencoding::encode(to), urlencoding::encode(msg));
    let res: Response = spin_sdk::http::send::<_, Response>(Request::builder().method(Method::Post).uri(format!("https://api.twilio.com/2010-04-01/Accounts/{}/Messages.json", sid)).header("Authorization", &format!("Basic {}", auth)).header("Content-Type", "application/x-www-form-urlencoded").body(body.into_bytes()).build()).await?;
    if !(200..300).contains(res.status()) { return Err(anyhow::anyhow!("Twilio: {}", res.status())); }
    Ok(())
}

fn local_hour_from_timezone(tz_name: &str, now: &chrono::DateTime<chrono::Utc>) -> u32 { let tz: chrono_tz::Tz = tz_name.parse().unwrap_or(chrono_tz::UTC); now.with_timezone(&tz).hour() }
fn aggregate_step_count(rs: &Vec<spin_sdk::pg::Row>) -> i32 { rs.iter().filter_map(|r| match &r[0] { DbValue::Str(s) => s.parse::<i32>().ok(), _ => None }).max().unwrap_or(0) }
fn should_dispatch(h: u32, s: i32, m: Option<u64>, _p: &NotificationPrefs) -> bool { if h < 9 || h >= 21 || s >= 2000 { false } else { m.map_or(true, |v| v >= 120) } }

async fn decrypt_token(enc_hex: &str) -> anyhow::Result<String> {
    let key_str = variables::get("master_encryption_key")?;
    let key_bytes = hex::decode(key_str.trim())?;
    let cipher = Aes256Gcm::new_from_slice(&key_bytes).map_err(|_| anyhow::anyhow!("cipher"))?;
    let enc_bytes = hex::decode(enc_hex.trim())?;
    if enc_bytes.len() < 12 { return Err(anyhow::anyhow!("Short")); }
    let nonce = Nonce::from_slice(&enc_bytes[..12]);
    let ct = &enc_bytes[12..];
    let dec = cipher.decrypt(nonce, ct).map_err(|_| anyhow::anyhow!("Dec fail"))?;
    Ok(String::from_utf8(dec)?)
}

async fn encrypt_token(plain: &str) -> anyhow::Result<String> {
    let key_str = variables::get("master_encryption_key")?;
    let key_bytes = hex::decode(key_str.trim())?;
    let cipher = Aes256Gcm::new_from_slice(&key_bytes).map_err(|_| anyhow::anyhow!("cipher"))?;
    let mut nonce_bytes = [0u8; 12]; getrandom::getrandom(&mut nonce_bytes).map_err(|_| anyhow::anyhow!("rand"))?;
    let nonce = Nonce::from_slice(&nonce_bytes);
    let ct = cipher.encrypt(nonce, plain.as_bytes()).map_err(|_| anyhow::anyhow!("Enc fail"))?;
    let mut comb = nonce_bytes.to_vec(); comb.extend_from_slice(&ct);
    Ok(hex::encode(comb))
}

async fn extract_user_id(auth: Option<&str>) -> Option<String> {
    if let Ok(bypass) = variables::get("auth_bypass") {
        if bypass == "true" {
            if let Some(h) = auth {
                let token = h.strip_prefix("Bearer ").unwrap_or(h);
                if token.starts_with("TestUser ") {
                    return Some(token[9..].to_string());
                }
            }
        }
    }
    let val = auth?;
    if !val.starts_with("Bearer ") { return None; }
    let tok = &val[7..]; let manual = variables::get("oidc_jwks_json").ok()?;
    let jwks: Jwks = serde_json::from_str(&manual).ok()?;
    let parts: Vec<&str> = tok.split('.').collect();
    if parts.len() != 3 { return None; }
    let header: serde_json::Value = serde_json::from_slice(&URL_SAFE_NO_PAD.decode(parts[0]).ok()?).ok()?;
    let kid = header["kid"].as_str()?; let jwk = jwks.keys.iter().find(|k| k.kid == kid)?;
    let options = VerificationOptions { accept_future: true, ..Default::default() };
    if jwk.kty == "EC" && jwk.alg == "ES384" {
        let n = URL_SAFE_NO_PAD.decode(&jwk.n).ok()?; let e = URL_SAFE_NO_PAD.decode(&jwk.e).ok()?;
        let mut pk_b = vec![0x04]; pk_b.extend_from_slice(&n); pk_b.extend_from_slice(&e);
        let pk = ES384PublicKey::from_bytes(&pk_b).ok()?;
        let claims = pk.verify_token::<serde_json::Value>(tok, Some(options)).ok()?;
        claims.subject.or_else(|| claims.custom["sub"].as_str().map(|s| s.to_string()))
    } else if jwk.kty == "RSA" && jwk.alg == "RS256" {
        let n = match URL_SAFE_NO_PAD.decode(&jwk.n) { Ok(b) => b, Err(_) => base64::engine::general_purpose::STANDARD.decode(&jwk.n).ok()? };
        let e = match URL_SAFE_NO_PAD.decode(&jwk.e) { Ok(b) => b, Err(_) => base64::engine::general_purpose::STANDARD.decode(&jwk.e).ok()? };
        let pk = RS256PublicKey::from_components(&n, &e).ok()?;
        let claims = pk.verify_token::<serde_json::Value>(tok, Some(options)).ok()?;
        claims.subject.or_else(|| claims.custom["sub"].as_str().map(|s| s.to_string()))
    } else { None }
}

async fn register_cloud_heartbeat(conn: &Connection, uid: &str) {
    let prov = variables::get("cloud_provider").unwrap_or_else(|_| "unknown".to_string());
    let role = match prov.as_str() { "akamai" => "akamai_functions", "fermyon" => "fermyon_cloud", _ => "unknown" };
    let _ = conn.execute("INSERT INTO scheduler_election (user_id, role, process_id, heartbeat) VALUES ($1, $2, $3, CURRENT_TIMESTAMP) ON CONFLICT (user_id, role) DO UPDATE SET heartbeat = EXCLUDED.heartbeat, process_id = EXCLUDED.process_id", &[ParameterValue::Str(uid.to_string()), ParameterValue::Str(role.to_string()), ParameterValue::Str(prov)]);
}

fn get_modality_status(role: &str, mins: u64) -> &'static str {
    match role { "leader" => if mins < 2 { "healthy" } else if mins < 5 { "degraded" } else { "offline" }, "android_client" => if mins < 20 { "healthy" } else if mins < 60 { "degraded" } else { "offline" }, "akamai_functions" => if mins < 135 { "healthy" } else if mins < 250 { "degraded" } else { "offline" }, "fermyon_cloud" => if mins < 5 { "healthy" } else if mins < 15 { "degraded" } else { "offline" }, _ => "unknown" }
}

async fn handle_weather_heuristic_get(_r: Request) -> anyhow::Result<Response> {
    #[derive(Serialize)] struct WeatherResp { conditions: String, description: String, temperature: f64, is_dark: bool, sunset_time: String, recommendation: String }
    json_response(200, &WeatherResp { conditions: "Clear".to_string(), description: "sunny".to_string(), temperature: 25.0, is_dark: false, sunset_time: "20:00".to_string(), recommendation: "Great day for a walk!".to_string() })
}

#[derive(Serialize)] struct StatusResponse { status: String, message: String }
#[derive(Deserialize, Serialize, Debug)] struct Jwks { keys: Vec<JwKey> }
#[derive(Deserialize, Serialize, Debug)] struct JwKey { kid: String, kty: String, alg: String, n: String, e: String }
