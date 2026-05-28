use spin_cron_sdk::cron_component;
use serde::{Deserialize, Serialize};
use spin_sdk::{
    http::{Request, Response, Method},
    http_service,
    pg::{Connection, ParameterValue, DbValue},
    variables,
};
use http_body_util::BodyExt;
use sha2::{Sha256, Digest};
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
use jwt_simple::prelude::*;
use aes_gcm::{aead::{Aead, KeyInit}, Aes256Gcm, Nonce};
use chrono::{Timelike, TimeZone};

#[derive(Deserialize, Default)] struct NotificationPrefs { #[allow(dead_code)] sms_opted_in: Option<bool> }
fn internal_api_key_ok(cfg: &str, h: Option<&str>) -> bool { if cfg.is_empty() { true } else { h == Some(cfg) } }
fn json_response<T: Serialize>(s: u16, d: &T) -> anyhow::Result<Response<String>> { Ok(Response::builder().status(s).header("content-type", "application/json").header("access-control-allow-origin", "*").body(serde_json::to_string(d)?)?) }
fn text_response(s: u16, t: &str) -> anyhow::Result<Response<String>> { Ok(Response::builder().status(s).header("access-control-allow-origin", "*").body(t.to_string())?) }
fn add_cors(mut r: Response<String>) -> Response<String> { r.headers_mut().insert("access-control-allow-origin", spin_sdk::http::HeaderValue::from_static("*")); r }

#[cron_component]
async fn handle_cron(_m: spin_cron_sdk::Metadata) -> anyhow::Result<()> {
    let db = match variables::get("db_url").await { Ok(v) if !v.is_empty() => v, _ => variables::get("neon_db_url").await? };
    let _ = run_clozemaster_scraper(&db, "c0a81a4b-115a-4eb6-bc2c-40908c58bf64").await;
    Ok(())
}

#[http_service]
async fn handle_sync_service(req: Request) -> anyhow::Result<Response<String>> {
    let path = req.uri().path(); let method = req.method();
    if method == &Method::OPTIONS { return Ok(Response::builder().status(204).header("access-control-allow-origin", "*").header("access-control-allow-methods", "GET, POST, PATCH, OPTIONS").header("access-control-allow-headers", "authorization, content-type, x-internal-api-key").body(String::new())?); }
    let resp = match (path, method) {
        ("/walks", &Method::POST) => handle_walks_post(req).await?,
        ("/budget", &Method::GET) => handle_budget_get(req).await?,
        ("/languages", &Method::GET) => handle_languages_get(req).await?,
        ("/languages/multiplier", &Method::POST) => handle_multiplier_post(req).await?,
        ("/health", &Method::GET) => handle_health_get(req).await?,
        ("/heartbeat", &Method::POST) => handle_heartbeat_post(req).await?,
        ("/internal/cloud-sync", &Method::POST) => handle_cloud_sync(req).await?,
        ("/aggregate-status", &Method::GET) => handle_aggregate_status_get(req).await?,
        ("/profile", &Method::POST) => handle_profile_post(req).await?,
        ("/profile", &Method::GET) => handle_profile_get(req).await?,
        ("/internal/trigger-reminders", _) => {
            let cfg = variables::get("internal_api_key").await.unwrap_or_default();
            let key = req.headers().get("x-internal-api-key").and_then(|v| v.to_str().ok());
            if !internal_api_key_ok(&cfg, key) { text_response(401, "Unauthorized")? } else { handle_trigger_reminders_post(req).await? }
        },
        ("/internal/failover-sync", _) => {
            let cfg = variables::get("internal_api_key").await.unwrap_or_default();
            let key = req.headers().get("x-internal-api-key").and_then(|v| v.to_str().ok());
            if !internal_api_key_ok(&cfg, key) { text_response(401, "Unauthorized")? } else { handle_failover_sync_post(req).await? }
        },
        ("/internal/weather-heuristic", &Method::GET) => handle_weather_heuristic_get(req).await?,
        ("/internal/request-phone-verification", &Method::POST) => handle_request_phone_verification_post(req).await?,
        ("/internal/confirm-phone-verification", &Method::POST) => handle_confirm_phone_verification_post(req).await?,
        ("/internal/twilio-webhook", &Method::POST) => handle_twilio_webhook_post(req).await?,
        _ => text_response(404, "Not Found")?,
    };
    Ok(add_cors(resp))
}

async fn handle_aggregate_status_get(req: Request) -> anyhow::Result<Response<String>> {
    let uid = match extract_user_id(req.headers().get("authorization")).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let full = req.uri().query().map(|q| q.contains("full=true")).unwrap_or(false);
    let db = match variables::get("db_url").await { Ok(v) if !v.is_empty() => v, _ => variables::get("neon_db_url").await? };
    let conn = Connection::open(&db).await?;
    let walk_rs = conn.query("SELECT COUNT(*) FROM walk_inferences WHERE (start_time::TIMESTAMPTZ AT TIME ZONE 'US/Eastern')::DATE = (CURRENT_TIMESTAMP AT TIME ZONE 'US/Eastern')::DATE AND CAST(step_count AS INTEGER) >= 2000 AND user_id = $1", &[ParameterValue::Str(uid.clone())]).await?.collect().await?;
    let walked = !walk_rs.is_empty() && match &walk_rs[0][0] { DbValue::Int64(i) => *i > 0, _ => false };
    let lang_rows = conn.query("SELECT language_name, current_reviews, tomorrow_reviews, pump_multiplier::FLOAT8, daily_completions FROM language_stats WHERE user_id = $1", &[ParameterValue::Str(uid.clone())]).await?.collect().await?;
    let user_rows = conn.query("SELECT vacation_mode_until::TEXT, phone_verified FROM users WHERE pocket_id_sub = $1", &[ParameterValue::Str(uid.clone())]).await?.collect().await?;
    let (vaca, phone) = if !user_rows.is_empty() { (match &user_rows[0][0] { DbValue::Str(s) => Some(s.clone()), _ => None }, match &user_rows[0][1] { DbValue::Boolean(b) => *b, _ => false }) } else { (None, false) };
    let mut total_goals = 1; let mut goals_met = if walked { 1 } else { 0 };
    let (mut arabic_met, mut greek_met) = (false, false);
    for r in &lang_rows {
        let n = match &r[0] { DbValue::Str(s) => s.clone(), _ => continue };
        let (cur, tom, mult, done) = (match &r[1] { DbValue::Int32(i) => *i, _ => 0 }, match &r[2] { DbValue::Int32(i) => *i, _ => 0 }, match &r[3] { DbValue::Floating64(f) => *f, _ => 1.0 }, match &r[4] { DbValue::Int32(i) => *i, _ => 0 });
        let (_, _, met) = calculate_targets(cur, tom, mult, done);
        if n == "ARABIC" { total_goals += 1; arabic_met = met; if met { goals_met += 1; } }
        else if n == "GREEK" { total_goals += 1; greek_met = met; if met { goals_met += 1; } }
    }
    #[derive(Serialize)] struct Comp { walk: bool, arabic: bool, greek: bool }
    #[derive(Serialize)] struct Mod { role: String, status: String, last_seen: String }
    #[derive(Serialize)] struct AggResp { score: String, goals_met: i32, total_goals: i32, all_clear: bool, components: Comp, vacation_mode_until: Option<String>, phone_verified: bool, modalities: Option<Vec<Mod>> }
    let mut mods = None;
    if full {
        let p_rows = conn.query("SELECT role, heartbeat::TEXT, CAST(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - heartbeat)) / 60 AS BIGINT) AS mins FROM scheduler_election WHERE user_id = $1 OR user_id IS NULL ORDER BY heartbeat DESC", &[ParameterValue::Str(uid.clone())]).await?.collect().await?;
        let mut ms = Vec::new();
        for r in &p_rows {
            let role = match &r[0] { DbValue::Str(s) => s.clone(), _ => continue };
            let display = match role.as_str() { "leader" => "MCP SERVER", "android_client" => "ANDROID", "akamai_functions" => "AKAMAI", "fermyon_cloud" => "FERMYON", _ => &role };
            let mins = match &r[2] { DbValue::Int64(i) => *i as u64, _ => 9999 };
            ms.push(Mod { role: display.to_string(), status: get_modality_status(&role, mins).to_string(), last_seen: match &r[1] { DbValue::Str(s) => s.clone(), _ => "never".to_string() } });
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

async fn handle_profile_post(req: Request) -> anyhow::Result<Response<String>> {
    let uid = match extract_user_id(req.headers().get("authorization")).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let body = req.into_body().collect().await.map_err(|e| anyhow::anyhow!("Body: {:?}", e))?.to_bytes();
    #[derive(Deserialize)] struct ProfReq { phone_number: Option<String>, beeminder_user: Option<String>, latitude: Option<f64>, longitude: Option<f64>, vacation_mode: Option<bool>, autonomous_sync_enabled: Option<bool>, notification_prefs: Option<serde_json::Value> }
    let pr: ProfReq = serde_json::from_slice(&body)?;
    let db = match variables::get("db_url").await { Ok(v) if !v.is_empty() => v, _ => variables::get("neon_db_url").await? };
    let conn = Connection::open(&db).await?;
    if let Some(p) = &pr.phone_number { let enc = encrypt_token(p).await?; conn.execute("UPDATE users SET phone_number_encrypted = $1, phone_verified = FALSE WHERE pocket_id_sub = $2", &[ParameterValue::Str(enc), ParameterValue::Str(uid.clone())]).await?; }
    if let Some(bu) = &pr.beeminder_user { let enc = encrypt_token(bu).await?; conn.execute("UPDATE users SET beeminder_user_encrypted = $1 WHERE pocket_id_sub = $2", &[ParameterValue::Str(enc), ParameterValue::Str(uid.clone())]).await?; }
    if let Some(lat) = pr.latitude { conn.execute("UPDATE users SET location_lat = $1 WHERE pocket_id_sub = $2", &[ParameterValue::Floating64(lat), ParameterValue::Str(uid.clone())]).await?; }
    if let Some(lon) = pr.longitude { conn.execute("UPDATE users SET location_lon = $1 WHERE pocket_id_sub = $2", &[ParameterValue::Floating64(lon), ParameterValue::Str(uid.clone())]).await?; }
    if let Some(vac) = pr.vacation_mode { if !vac { conn.execute("UPDATE users SET vacation_mode_until = NULL WHERE pocket_id_sub = $1", &[ParameterValue::Str(uid.clone())]).await?; } else { let u = (chrono::Utc::now() + chrono::Duration::days(1)).to_rfc3339(); conn.execute("UPDATE users SET vacation_mode_until = $1::TIMESTAMPTZ WHERE pocket_id_sub = $2", &[ParameterValue::Str(u), ParameterValue::Str(uid.clone())]).await?; } }
    if let Some(sync) = pr.autonomous_sync_enabled { conn.execute("UPDATE users SET autonomous_sync_enabled = $1 WHERE pocket_id_sub = $2", &[ParameterValue::Boolean(sync), ParameterValue::Str(uid.clone())]).await?; }
    if let Some(pref) = &pr.notification_prefs { conn.execute("UPDATE users SET notification_prefs = $1::JSONB WHERE pocket_id_sub = $2", &[ParameterValue::Str(serde_json::to_string(pref)?), ParameterValue::Str(uid.clone())]).await?; }
    json_response(200, &StatusResponse { status: "success".to_string(), message: "Profile updated".to_string() })
}

async fn handle_profile_get(req: Request) -> anyhow::Result<Response<String>> {
    let uid = match extract_user_id(req.headers().get("authorization")).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let db = match variables::get("db_url").await { Ok(v) if !v.is_empty() => v, _ => variables::get("neon_db_url").await? };
    let conn = Connection::open(&db).await?;
    let rs = conn.query("SELECT phone_number_encrypted, beeminder_user_encrypted, location_lat, location_lon, vacation_mode_until::TEXT, autonomous_sync_enabled FROM users WHERE pocket_id_sub = $1", &[ParameterValue::Str(uid.clone())]).await?.collect().await?;
    if rs.is_empty() { return Ok(text_response(404, "User not found")?); }
    #[derive(Serialize)] struct ProfResp { phone_number: Option<String>, beeminder_user: Option<String>, latitude: Option<f64>, longitude: Option<f64>, vacation_mode_until: Option<String>, autonomous_sync_enabled: bool }
    let r = &rs[0];
    let p = match &r[0] { DbValue::Str(s) if !s.is_empty() => decrypt_token(s).await.ok(), _ => None };
    let bu = match &r[1] { DbValue::Str(s) if !s.is_empty() => decrypt_token(s).await.ok(), _ => None };
    json_response(200, &ProfResp { phone_number: p, beeminder_user: bu, latitude: match &r[2] { DbValue::Floating64(f) => Some(*f), _ => None }, longitude: match &r[3] { DbValue::Floating64(f) => Some(*f), _ => None }, vacation_mode_until: match &r[4] { DbValue::Str(s) if !s.is_empty() => Some(s.clone()), _ => None }, autonomous_sync_enabled: match &r[5] { DbValue::Boolean(b) => *b, _ => false } })
}

async fn handle_cloud_sync(req: Request) -> anyhow::Result<Response<String>> {
    let uid = match extract_user_id(req.headers().get("authorization")).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let db = match variables::get("db_url").await { Ok(v) if !v.is_empty() => v, _ => variables::get("neon_db_url").await? };
    let _ = run_clozemaster_scraper(&db, &uid).await;
    json_response(200, &StatusResponse { status: "success".to_string(), message: "Sync initiated".to_string() })
}

async fn handle_health_get(req: Request) -> anyhow::Result<Response<String>> {
    let uid = match extract_user_id(req.headers().get("authorization")).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let db = match variables::get("db_url").await { Ok(v) if !v.is_empty() => v, _ => variables::get("neon_db_url").await? };
    let conn = Connection::open(&db).await?;
    let _ = register_cloud_heartbeat(&conn, &uid).await;
    #[derive(Serialize)] struct HealthResp { status: String, home_server_active: bool, leader_pid: String, last_seen: String }
    let mut active = false; let mut pid = "none".to_string(); let mut last = "never".to_string();
    let rs = conn.query("SELECT (heartbeat > CURRENT_TIMESTAMP - INTERVAL '90 seconds') as is_fresh, heartbeat::TEXT, process_id FROM scheduler_election WHERE user_id = $1 AND role = 'leader'", &[ParameterValue::Str(uid)]).await?.collect().await?;
    if !rs.is_empty() { active = match &rs[0][0] { DbValue::Boolean(b) => *b, _ => false }; last = match &rs[0][1] { DbValue::Str(s) => s.clone(), _ => "unknown".to_string() }; pid = match &rs[0][2] { DbValue::Str(s) => s.clone(), _ => "unknown".to_string() }; }
    json_response(200, &HealthResp { status: "ok".to_string(), home_server_active: active, leader_pid: pid, last_seen: last })
}

async fn handle_heartbeat_post(req: Request) -> anyhow::Result<Response<String>> {
    let uid = match extract_user_id(req.headers().get("authorization")).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let body = req.into_body().collect().await.map_err(|e| anyhow::anyhow!("Body: {:?}", e))?.to_bytes();
    let b: serde_json::Value = serde_json::from_slice(&body)?;
    let pid = b.get("process_id").and_then(|v| v.as_str()).unwrap_or("unknown");
    let role = b.get("role").and_then(|v| v.as_str()).unwrap_or("leader");
    let db = match variables::get("db_url").await { Ok(v) if !v.is_empty() => v, _ => variables::get("neon_db_url").await? };
    let conn = Connection::open(&db).await?;
    conn.execute("INSERT INTO scheduler_election (user_id, role, process_id, heartbeat) VALUES ($1, $2, $3, CURRENT_TIMESTAMP) ON CONFLICT (user_id, role) DO UPDATE SET heartbeat = EXCLUDED.heartbeat, process_id = EXCLUDED.process_id", &[ParameterValue::Str(uid), ParameterValue::Str(role.to_string()), ParameterValue::Str(pid.to_string())]).await?;
    json_response(200, &StatusResponse { status: "success".to_string(), message: "Heartbeat received".to_string() })
}

async fn handle_multiplier_post(req: Request) -> anyhow::Result<Response<String>> {
    let uid = match extract_user_id(req.headers().get("authorization")).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let body = req.into_body().collect().await.map_err(|e| anyhow::anyhow!("Body: {:?}", e))?.to_bytes();
    #[derive(Deserialize)] struct MultReq { name: String, multiplier: f64 }
    let data: MultReq = serde_json::from_slice(&body)?;
    let db = match variables::get("db_url").await { Ok(v) if !v.is_empty() => v, _ => variables::get("neon_db_url").await? };
    let conn = Connection::open(&db).await?;
    match conn.execute("UPDATE language_stats SET pump_multiplier = $1::FLOAT8::NUMERIC WHERE user_id = $2 AND language_name = $3", &[ParameterValue::Floating64(data.multiplier), ParameterValue::Str(uid), ParameterValue::Str(data.name.to_uppercase())]).await {
        Ok(_) => Ok(text_response(200, "Multiplier updated")?),
        Err(e) => json_response(500, &StatusResponse { status: "error".to_string(), message: format!("DB: {}", e) })
    }
}

async fn handle_languages_get(req: Request) -> anyhow::Result<Response<String>> {
    let uid = match extract_user_id(req.headers().get("authorization")).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let db = match variables::get("db_url").await { Ok(v) if !v.is_empty() => v, _ => variables::get("neon_db_url").await? };
    let conn = Connection::open(&db).await?;
    let rs = conn.query("SELECT language_name, current_reviews, tomorrow_reviews, next_7_days_reviews, daily_rate::FLOAT8, safebuf, derail_risk, pump_multiplier::FLOAT8, beeminder_slug, daily_completions FROM language_stats WHERE user_id = $1 ORDER BY (beeminder_slug != '') DESC, language_name ASC", &[ParameterValue::Str(uid)]).await?.collect().await?;
    #[derive(Serialize)] struct LangStat { name: String, current: i32, tomorrow: i32, next_7_days: i32, daily_rate: f64, safebuf: i32, derail_risk: String, pump_multiplier: Option<f64>, daily_completions: i32, goal_met: bool, absolute_target: i32 }
    let mut langs = Vec::new();
    for r in &rs {
        let (name, cur, tom, n7, rate, sb, risk, mult, done) = (match &r[0] { DbValue::Str(s) => s.clone(), _ => continue }, match &r[1] { DbValue::Int32(i) => *i, _ => 0 }, match &r[2] { DbValue::Int32(i) => *i, _ => 0 }, match &r[3] { DbValue::Int32(i) => *i, _ => 0 }, match &r[4] { DbValue::Floating64(f) => *f, _ => 0.0 }, match &r[5] { DbValue::Int32(i) => *i, _ => 0 }, match &r[6] { DbValue::Str(s) => s.clone(), _ => "unknown".to_string() }, match &r[7] { DbValue::Floating64(f) => Some(*f), _ => None }, match &r[9] { DbValue::Int32(i) => *i, _ => 0 });
        let (target, _, met) = calculate_targets(cur, tom, mult.unwrap_or(1.0), done);
        langs.push(LangStat { name, current: cur, tomorrow: tom, next_7_days: n7, daily_rate: rate, safebuf: sb, derail_risk: risk, pump_multiplier: mult, daily_completions: done, goal_met: met, absolute_target: target });
    }
    #[derive(Serialize)] struct LangResp { languages: Vec<LangStat> }
    json_response(200, &LangResp { languages: langs })
}

async fn handle_budget_get(req: Request) -> anyhow::Result<Response<String>> {
    let uid = match extract_user_id(req.headers().get("authorization")).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let db = match variables::get("db_url").await { Ok(v) if !v.is_empty() => v, _ => variables::get("neon_db_url").await? };
    let conn = Connection::open(&db).await?;
    let rs = conn.query("SELECT remaining_budget FROM budget_tracking WHERE user_id = $1 LIMIT 1", &[ParameterValue::Str(uid)]).await?.collect().await?;
    let budget = if rs.is_empty() { 0.0 } else { match &rs[0][0] { DbValue::Floating64(f) => *f, _ => 0.0 } };
    #[derive(Serialize)] struct BudgetResp { remaining_budget: f64 }
    json_response(200, &BudgetResp { remaining_budget: budget })
}

async fn handle_walks_post(req: Request) -> anyhow::Result<Response<String>> {
    let uid = match extract_user_id(req.headers().get("authorization")).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let body = req.into_body().collect().await.map_err(|e| anyhow::anyhow!("Body: {:?}", e))?.to_bytes();
    #[derive(Deserialize)] struct WalkSum { start_time: String, end_time: String, step_count: i32, distance_meters: f64, distance_source: String, confidence_score: f64, gps_route_points: i32 }
    let walk: WalkSum = serde_json::from_slice(&body)?;
    let db = match variables::get("db_url").await { Ok(v) if !v.is_empty() => v, _ => variables::get("neon_db_url").await? };
    let conn = Connection::open(&db).await?;
    let _ = conn.execute("INSERT INTO users (pocket_id_sub, beeminder_token_encrypted, beeminder_goal) VALUES ($1, '', 'bike') ON CONFLICT DO NOTHING", &[ParameterValue::Str(uid.clone())]).await;
    let prev = conn.query("SELECT distance_meters FROM walk_inferences WHERE user_id = $1 AND start_time = $2", &[ParameterValue::Str(uid.clone()), ParameterValue::Str(walk.start_time.clone())]).await?.collect().await?;
    let prev_dist: f64 = if !prev.is_empty() { match &prev[0][0] { DbValue::Str(s) => s.parse().unwrap_or(0.0), _ => 0.0 } } else { 0.0 };
    let delta = walk.distance_meters - prev_dist;
    conn.execute("INSERT INTO walk_inferences (user_id, start_time, end_time, step_count, distance_meters, distance_source, confidence_score, gps_route_points) VALUES ($1, $2, $3, $4, $5, $6, $7, $8) ON CONFLICT (user_id, start_time) DO UPDATE SET end_time = EXCLUDED.end_time, step_count = EXCLUDED.step_count, distance_meters = EXCLUDED.distance_meters, distance_source = EXCLUDED.distance_source, confidence_score = EXCLUDED.confidence_score, gps_route_points = EXCLUDED.gps_route_points", &[ParameterValue::Str(uid.clone()), ParameterValue::Str(walk.start_time.clone()), ParameterValue::Str(walk.end_time.clone()), ParameterValue::Str(walk.step_count.to_string()), ParameterValue::Str(walk.distance_meters.to_string()), ParameterValue::Str(walk.distance_source.clone()), ParameterValue::Str(walk.confidence_score.to_string()), ParameterValue::Str(walk.gps_route_points.to_string())]).await?;
    let token = conn.query("SELECT beeminder_goal FROM users WHERE pocket_id_sub = $1", &[ParameterValue::Str(uid.clone())]).await?.collect().await?;
    if !token.is_empty() && delta > 200.0 {
        let goal = match &token[0][0] { DbValue::Str(s) if !s.is_empty() => s.clone(), _ => "bike".to_string() };
        let miles = ((walk.distance_meters / 1609.34) * 1000.0).round() / 1000.0;
        let requestid = format!("{}-{}-{}-{}", uid, goal, walk.start_time, walk.distance_meters);
        let _ = push_to_beeminder_idempotent(&uid, &goal, miles, "Synced via Spin (Cumulative)", &requestid, &conn).await;
    }
    json_response(201, &StatusResponse { status: "success".to_string(), message: "Walk ingested".to_string() })
}

async fn handle_trigger_reminders_post(_req: Request) -> anyhow::Result<Response<String>> {
    let sid = variables::get("twilio_account_sid").await?;
    let _tok = decrypt_token(&variables::get("twilio_auth_token_encrypted").await?).await?;
    let from = variables::get("twilio_from_number").await?;
    let db = match variables::get("db_url").await { Ok(v) if !v.is_empty() => v, _ => variables::get("neon_db_url").await? };
    let conn = Connection::open(&db).await?;
    let rs = conn.query("SELECT pocket_id_sub, phone_number_encrypted, COALESCE(timezone, 'UTC'), COALESCE(notification_prefs::TEXT, '{}') FROM users WHERE phone_number_encrypted IS NOT NULL AND phone_number_encrypted != '' AND autonomous_sync_enabled = true", &[]).await?.collect().await?;
    let (mut sent, mut errors, now) = (0, 0, chrono::Utc::now());
    let (today, epoch) = (now.format("%Y-%m-%d").to_string(), now.timestamp() as u64);
    for r in &rs {
        let (uid, ph_enc, tz, pref_j) = (match &r[0] { DbValue::Str(s) => s.clone(), _ => continue }, match &r[1] { DbValue::Str(s) => s.clone(), _ => continue }, match &r[2] { DbValue::Str(s) => s.clone(), _ => "UTC".to_string() }, match &r[3] { DbValue::Str(s) => s.clone(), _ => "{}".to_string() });
        let pref: NotificationPrefs = serde_json::from_str(&pref_j).unwrap_or_default();
        let s_rs = conn.query("SELECT step_count FROM walk_inferences WHERE user_id = $1 AND start_time >= $2 ORDER BY start_time ASC", &[ParameterValue::Str(uid.clone()), ParameterValue::Str(today.clone())]).await?.collect().await?;
        let steps = aggregate_step_count(&s_rs);
        let m_rs = conn.query("SELECT sent_at::TEXT FROM message_log WHERE user_id = $1 AND type = 'walk_reminder' ORDER BY sent_at DESC LIMIT 1", &[ParameterValue::Str(uid.clone())]).await?.collect().await?;
        let ms = m_rs.first().and_then(|mr| match &mr[0] { DbValue::Str(s) if !s.is_empty() => Some(s.as_str()), _ => None });
        let mins = ms.and_then(|s| chrono::DateTime::parse_from_rfc3339(s).or_else(|_| chrono::DateTime::parse_from_str(s, "%Y-%m-%d %H:%M:%S%.f%z")).ok().map(|dt| epoch.saturating_sub(dt.timestamp() as u64) / 60));
        if !should_dispatch(local_hour_from_timezone(&tz, &now), steps, mins, &pref) { continue; }
        let hb_rs = conn.query("SELECT EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - heartbeat)) / 60 FROM scheduler_election WHERE user_id = $1 AND role = 'android_client' ORDER BY heartbeat DESC LIMIT 1", &[ParameterValue::Str(uid.clone())]).await?.collect().await?;
        if hb_rs.first().and_then(|hr| match &hr[0] { DbValue::Floating64(f) => Some(*f as u64), _ => None }).map_or(false, |m| m < 240) { continue; }
        let ph = decrypt_token(&ph_enc).await?;
        match send_twilio_sms(&sid, &_tok, &from, &ph, "Mecris: Time for a walk! Reply YES to log 1 mile.").await {
            Ok(_) => { let _ = conn.execute("INSERT INTO message_log (user_id, type, sent_at, compliance_status) VALUES ($1, 'walk_reminder', CURRENT_TIMESTAMP, 'sent')", &[ParameterValue::Str(uid.clone())]).await; sent += 1; }
            Err(_) => { errors += 1; }
        }
    }
    json_response(200, &format!("Sent {} reminders, {} errors", sent, errors))
}

async fn handle_failover_sync_post(_req: Request) -> anyhow::Result<Response<String>> {
    let db = match variables::get("db_url").await { Ok(v) if !v.is_empty() => v, _ => variables::get("neon_db_url").await? };
    let conn = Connection::open(&db).await?;
    let rs = conn.query("SELECT pocket_id_sub, EXTRACT(EPOCH FROM CURRENT_TIMESTAMP - COALESCE(last_autonomous_sync, '1970-01-01'::TIMESTAMPTZ))/60 FROM users WHERE autonomous_sync_enabled = true", &[]).await?.collect().await?;
    let mut success = 0;
    for r in &rs {
        let uid = match &r[0] { DbValue::Str(s) => s.clone(), _ => continue };
        let mins = match &r[1] { DbValue::Floating64(f) => *f, _ => 0.0 };
        if mins > 1440.0 { if let Ok(_) = run_clozemaster_scraper(&db, &uid).await { success += 1; } }
    }
    json_response(200, &format!("Failover sync: {} success", success))
}

async fn handle_request_phone_verification_post(req: Request) -> anyhow::Result<Response<String>> {
    let uid = match extract_user_id(req.headers().get("authorization")).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let body = req.into_body().collect().await.map_err(|_| anyhow::anyhow!("body"))?.to_bytes();
    #[derive(Deserialize)] struct Req { phone_number: String }
    let vr: Req = serde_json::from_slice(&body)?;
    let db = match variables::get("db_url").await { Ok(v) if !v.is_empty() => v, _ => variables::get("neon_db_url").await? };
    let conn = Connection::open(&db).await?;
    let mut rb = [0u8; 4]; getrandom::getrandom(&mut rb).map_err(|e| anyhow::anyhow!("getrandom: {}", e))?;
    let code = format!("{:06}", (u32::from_be_bytes(rb) % 1000000));
    let hash = hex::encode(Sha256::digest(code.as_bytes()));
    let exp = (chrono::Utc::now() + chrono::Duration::minutes(15)).to_rfc3339();
    conn.execute("INSERT INTO phone_verifications (user_id, code_hash, expires_at) VALUES ($1, $2, $3::TIMESTAMPTZ) ON CONFLICT (user_id) DO UPDATE SET code_hash = EXCLUDED.code_hash, expires_at = EXCLUDED.expires_at, attempts = 0", &[ParameterValue::Str(uid.clone()), ParameterValue::Str(hash), ParameterValue::Str(exp)]).await?;
    let sid = variables::get("twilio_account_sid").await?;
    let auth = decrypt_token(&variables::get("twilio_auth_token_encrypted").await?).await?;
    let from = variables::get("twilio_from_number").await?;
    send_twilio_sms(&sid, &auth, &from, &vr.phone_number, &format!("Mecris code: {}", code)).await?;
    json_response(200, &"Verification code sent")
}

async fn handle_confirm_phone_verification_post(req: Request) -> anyhow::Result<Response<String>> {
    let uid = match extract_user_id(req.headers().get("authorization")).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let body = req.into_body().collect().await.map_err(|_| anyhow::anyhow!("body"))?.to_bytes();
    #[derive(Deserialize)] struct Conf { code: String }
    let cr: Conf = serde_json::from_slice(&body)?;
    let db = match variables::get("db_url").await { Ok(v) if !v.is_empty() => v, _ => variables::get("neon_db_url").await? };
    let conn = Connection::open(&db).await?;
    let rs = conn.query("SELECT code_hash, CAST(EXTRACT(EPOCH FROM expires_at) AS BIGINT), attempts FROM phone_verifications WHERE user_id = $1", &[ParameterValue::Str(uid.clone())]).await?.collect().await?;
    if rs.is_empty() { return Ok(text_response(400, "No request")?); }
    let db_hash = match &rs[0][0] { DbValue::Str(s) => s, _ => "" };
    let exp = match &rs[0][1] { DbValue::Int64(i) => *i as u64, _ => 0 };
    let att = match &rs[0][2] { DbValue::Int32(i) => *i, _ => 0 };
    if att >= 5 { return Ok(text_response(429, "Too many attempts")?); }
    if chrono::Utc::now().timestamp() as u64 > exp { return Ok(text_response(400, "Expired")?); }
    if hex::encode(Sha256::digest(cr.code.as_bytes())) == db_hash {
        conn.execute("UPDATE users SET phone_verified = true WHERE pocket_id_sub = $1", &[ParameterValue::Str(uid.clone())]).await?;
        conn.execute("DELETE FROM phone_verifications WHERE user_id = $1", &[ParameterValue::Str(uid.clone())]).await?;
        json_response(200, &"Phone verified")
    } else {
        conn.execute("UPDATE phone_verifications SET attempts = attempts + 1 WHERE user_id = $1", &[ParameterValue::Str(uid.clone())]).await?;
        text_response(400, "Invalid code")
    }
}

async fn handle_twilio_webhook_post(req: Request) -> anyhow::Result<Response<String>> {
    let _tok = decrypt_token(&variables::get("twilio_auth_token_encrypted").await?).await?;
    let body = req.into_body().collect().await.map_err(|_| anyhow::anyhow!("body"))?.to_bytes();
    let body_str = std::str::from_utf8(&body).unwrap_or("");
    let from_num = body_str.split('&').find_map(|p| { let mut i = p.splitn(2, '='); if i.next() == Some("From") { Some(urlencoding::decode(&i.next()?.replace('+', " ")).unwrap_or_default().into_owned()) } else { None } }).unwrap_or_default();
    if body_str.to_uppercase().contains("YES") {
        let db = match variables::get("db_url").await { Ok(v) if !v.is_empty() => v, _ => variables::get("neon_db_url").await? };
        let conn = Connection::open(&db).await?;
        let rs = conn.query("SELECT pocket_id_sub, phone_number_encrypted, beeminder_goal FROM users WHERE phone_number_encrypted IS NOT NULL", &[]).await?.collect().await?;
        for r in &rs {
            let (uid, ph_enc, goal) = (match &r[0] { DbValue::Str(s) => s.clone(), _ => continue }, match &r[1] { DbValue::Str(s) => s.clone(), _ => continue }, match &r[2] { DbValue::Str(s) => s.clone(), _ => "bike".to_string() });
            if let Ok(ph) = decrypt_token(&ph_enc).await {
                let clean = |s: &str| s.chars().filter(|c| c.is_digit(10)).collect::<String>();
                if !ph.is_empty() && clean(&ph) == clean(&from_num) {
                    let requestid = format!("{}-{}-{}-sms", uid, goal, chrono::Utc::now().format("%Y-%m-%d"));
                    let _ = push_to_beeminder_idempotent(&uid, &goal, 1.0, "Walk logged via SMS", &requestid, &conn).await;
                    let _ = conn.execute("INSERT INTO message_log (user_id, type, sent_at, compliance_status) VALUES ($1, 'walk_ack', CURRENT_TIMESTAMP, 'received')", &[ParameterValue::Str(uid)]).await;
                }
            }
        }
    }
    Ok(Response::builder().status(200).header("content-type", "text/xml").body(r#"<?xml version="1.0" encoding="UTF-8"?><Response></Response>"#.to_string())?)
}

async fn run_clozemaster_scraper(db: &str, uid: &str) -> anyhow::Result<()> {
    let conn = Connection::open(db).await?;
    let rs = conn.query("SELECT clozemaster_email_encrypted, clozemaster_password_encrypted FROM users WHERE pocket_id_sub = $1", &[ParameterValue::Str(uid.to_string())]).await?.collect().await?;
    if rs.is_empty() { return Err(anyhow::anyhow!("User not found")); }
    let email = decrypt_token(match &rs[0][0] { DbValue::Str(s) => s, _ => "" }).await?;
    let pass = decrypt_token(match &rs[0][1] { DbValue::Str(s) => s, _ => "" }).await?;
    let ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36";
    let res = spin_sdk::http::send(Request::builder().method(Method::GET).uri("https://www.clozemaster.com/login").header("User-Agent", ua).body(String::new())?).await?;
    let sess = res.headers().get("set-cookie").and_then(|v| v.to_str().ok()).unwrap_or("").split(';').next().unwrap_or("").to_string();
    let body = String::from_utf8(res.into_body().collect().await.map_err(|_| anyhow::anyhow!("body"))?.to_bytes().to_vec())?;
    let csrf = regex::Regex::new(r#"name="authenticity_token" value="([^"]*)""#)?.captures(&body).and_then(|cap| cap.get(1)).map(|m| m.as_str()).ok_or_else(|| anyhow::anyhow!("CSRF"))?;
    let login_body = format!("user%5Blogin%5D={}&user%5Bpassword%5D={}&authenticity_token={}&commit=Log+In", urlencoding::encode(&email), urlencoding::encode(&pass), urlencoding::encode(csrf));
    let res = spin_sdk::http::send(Request::builder().method(Method::POST).uri("https://www.clozemaster.com/login").header("content-type", "application/x-www-form-urlencoded").header("User-Agent", ua).header("Cookie", &sess).body(login_body)?).await?;
    let sess = res.headers().get("set-cookie").and_then(|v| v.to_str().ok()).unwrap_or(&sess).split(';').next().unwrap_or(&sess).to_string();
    let mut res = spin_sdk::http::send(Request::builder().method(Method::GET).uri("https://www.clozemaster.com/dashboard").header("User-Agent", ua).header("Cookie", &sess).body(String::new())?).await?;
    if res.status().as_u16() == 302 { if let Some(loc) = res.headers().get("location").and_then(|v| v.to_str().ok()) { let url = if loc.starts_with('/') { format!("https://www.clozemaster.com{}", loc) } else { loc.to_string() }; res = spin_sdk::http::send(Request::builder().method(Method::GET).uri(url).header("User-Agent", ua).header("Cookie", &sess).body(String::new())?).await?; } }
    let body = String::from_utf8(res.into_body().collect().await.map_err(|_| anyhow::anyhow!("body"))?.to_bytes().to_vec())?;
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
            let (lang, beem) = match slug_name.as_str() { 
                "ara-eng" => ("ARABIC", "reviewstack"), 
                "ell-eng" => ("GREEK", ""), 
                "gle-eng" => ("IRISH", ""),
                "tok-eng" => ("TOKI PONA", ""),
                "lit-eng" => ("LITHUANIAN", ""),
                "swh-eng" => ("SWAHILI", ""),
                _ => (slug_name.as_str(), ""), 
            };
            let (mut tom, mut n7) = (0, 0);
            if id > 0 {
                let api_url = format!("https://www.clozemaster.com/api/v1/lp/{}/more-stats", id);
                if let Ok(api_res) = spin_sdk::http::send(Request::builder().method(Method::GET).uri(api_url).header("User-Agent", ua).header("Cookie", &sess).header("X-CSRF-Token", fresh_csrf).header("X-Requested-With", "XMLHttpRequest").body(String::new())?).await {
                    let api_json: serde_json::Value = serde_json::from_str(&String::from_utf8(api_res.into_body().collect().await.map_err(|_| anyhow::anyhow!("body"))?.to_bytes().to_vec())?)?;
                    if let Some(f) = api_json.get("reviewForecast").and_then(|v| v.as_array()) { if !f.is_empty() {
                        let parse = |v: &serde_json::Value| v.get("count").and_then(|v| v.as_i64()).unwrap_or_else(|| v.as_i64().unwrap_or(0)) as i32;
                        tom = parse(&f[0]); n7 = f.iter().take(7).map(parse).sum();
                    } }
                }
            }
            let rs = conn.query("SELECT current_reviews, (beeminder_last_sync AT TIME ZONE 'UTC')::TEXT FROM language_stats WHERE user_id = $1 AND language_name = $2", &[ParameterValue::Str(uid.to_string()), ParameterValue::Str(lang.to_uppercase())]).await?.collect().await?;
            let (mut prev, mut lsync) = (-1, String::new());
            if !rs.is_empty() { prev = match &rs[0][0] { DbValue::Int32(i) => *i, _ => -1 }; lsync = match &rs[0][1] { DbValue::Str(s) => s.clone(), _ => String::new() }; }
            let mut compl = tod; if lang == "ARABIC" { compl = (tod as f64 / 16.0) as i32; }
            conn.execute("INSERT INTO language_stats (user_id, language_name, current_reviews, tomorrow_reviews, next_7_days_reviews, beeminder_slug, daily_completions, last_points, total_points, last_updated) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, CURRENT_TIMESTAMP) ON CONFLICT (user_id, language_name) DO UPDATE SET current_reviews = EXCLUDED.current_reviews, tomorrow_reviews = EXCLUDED.tomorrow_reviews, next_7_days_reviews = EXCLUDED.next_7_days_reviews, beeminder_slug = EXCLUDED.beeminder_slug, daily_completions = EXCLUDED.daily_completions, last_points = EXCLUDED.last_points, total_points = EXCLUDED.total_points, last_updated = CURRENT_TIMESTAMP", &[ParameterValue::Str(uid.to_string()), ParameterValue::Str(lang.to_uppercase()), ParameterValue::Int32(cur), ParameterValue::Int32(tom), ParameterValue::Int32(n7), ParameterValue::Str(beem.to_string()), ParameterValue::Int32(compl), ParameterValue::Int32(tot), ParameterValue::Int32(tot)]).await?;
            if !beem.is_empty() {
                let now_ny = chrono::Utc::now().with_timezone(&chrono_tz::America::New_York);
                let today_ny = now_ny.format("%Y-%m-%d").to_string();
                let already_synced = if lsync.is_empty() { false } else { match chrono::NaiveDateTime::parse_from_str(lsync.split('.').next().unwrap_or(""), "%Y-%m-%d %H:%M:%S") { Ok(ndt) => chrono::Utc.from_utc_datetime(&ndt).with_timezone(&chrono_tz::America::New_York).format("%Y-%m-%d").to_string() == today_ny, Err(_) => false } };
                if cur != prev || !already_synced {
                    let comment = format!("Auto-synced from Clozemaster (Cloud) at {} | Tomorrow: {} | 7-day: {}", now_ny.format("%Y-%m-%d %H:%M"), tom, n7);
                    let rid = format!("{}-{}-{}-{}", uid, beem, today_ny, cur);
                    if let Ok(_) = push_to_beeminder_idempotent(uid, beem, cur as f64, &comment, &rid, &conn).await { conn.execute("UPDATE language_stats SET beeminder_last_sync = CURRENT_TIMESTAMP WHERE user_id = $1 AND language_name = $2", &[ParameterValue::Str(uid.to_string()), ParameterValue::Str(lang.to_uppercase())]).await?; }
                }
                if let Ok((mut sb, mut risk, rate)) = fetch_from_beeminder(uid, beem, &conn).await {
                    if cur == 0 && tom == 0 && n7 == 0 { sb = 999; risk = "SAFE".to_string(); }
                    conn.execute("UPDATE language_stats SET safebuf = $1, derail_risk = $2, daily_rate = $3::FLOAT8::NUMERIC WHERE user_id = $4 AND language_name = $5", &[ParameterValue::Int32(sb), ParameterValue::Str(risk), ParameterValue::Floating64(rate), ParameterValue::Str(uid.to_string()), ParameterValue::Str(lang.to_uppercase())]).await?;
                }
            }
        }
    }
    Ok(())
}

async fn fetch_from_beeminder(uid: &str, slug: &str, conn: &Connection) -> anyhow::Result<(i32, String, f64)> {
    let rs = conn.query("SELECT beeminder_token_encrypted, beeminder_user_encrypted FROM users WHERE pocket_id_sub = $1", &[ParameterValue::Str(uid.to_string())]).await?.collect().await?;
    if rs.is_empty() { return Err(anyhow::anyhow!("User")); }
    let tok = decrypt_token(match &rs[0][0] { DbValue::Str(s) => s, _ => "" }).await?;
    let user = if let DbValue::Str(s) = &rs[0][1] { if !s.is_empty() { decrypt_token(s).await? } else { "me".to_string() } } else { "me".to_string() };
    let res = spin_sdk::http::send(Request::builder().method(Method::GET).uri(format!("https://www.beeminder.com/api/v1/users/{}/goals/{}.json?auth_token={}", user, slug, tok)).body(String::new())?).await?;
    let data: serde_json::Value = serde_json::from_str(&String::from_utf8(res.into_body().collect().await.map_err(|_| anyhow::anyhow!("body"))?.to_bytes().to_vec())?)?;
    let sb = data.get("safebuf").and_then(|v| v.as_i64()).unwrap_or(0) as i32;
    let rate = data.get("rate").and_then(|v| v.as_f64()).unwrap_or(0.0);
    let risk = if sb <= 0 { "CRITICAL" } else if sb == 1 { "WARNING" } else if sb <= 3 { "CAUTION" } else { "SAFE" };
    Ok((sb, risk.to_string(), rate))
}

async fn push_to_beeminder_idempotent(uid: &str, slug: &str, val: f64, comment: &str, rid: &str, conn: &Connection) -> anyhow::Result<()> {
    let rs = conn.query("SELECT beeminder_token_encrypted, beeminder_user_encrypted FROM users WHERE pocket_id_sub = $1", &[ParameterValue::Str(uid.to_string())]).await?.collect().await?;
    if rs.is_empty() { return Err(anyhow::anyhow!("User")); }
    let tok = decrypt_token(match &rs[0][0] { DbValue::Str(s) => s, _ => "" }).await?;
    let user = if let DbValue::Str(s) = &rs[0][1] { if !s.is_empty() { decrypt_token(s).await? } else { "me".to_string() } } else { "me".to_string() };
    let body = format!("auth_token={}&value={}&comment={}&requestid={}", tok, val, urlencoding::encode(comment), urlencoding::encode(rid));
    let res = spin_sdk::http::send(Request::builder().method(Method::POST).uri(format!("https://www.beeminder.com/api/v1/users/{}/goals/{}/datapoints.json", user, slug)).header("content-type", "application/x-www-form-urlencoded").body(body)?).await?;
    if res.status().as_u16() == 422 { return Ok(()); }
    if !(200..300).contains(&res.status().as_u16()) { return Err(anyhow::anyhow!("Push fail: {}", res.status())); }
    Ok(())
}

async fn push_to_beeminder(uid: &str, slug: &str, val: f64, comment: &str, conn: &Connection) -> anyhow::Result<()> {
    let rs = conn.query("SELECT beeminder_token_encrypted, beeminder_user_encrypted FROM users WHERE pocket_id_sub = $1", &[ParameterValue::Str(uid.to_string())]).await?.collect().await?;
    if rs.is_empty() { return Err(anyhow::anyhow!("User")); }
    let tok = decrypt_token(match &rs[0][0] { DbValue::Str(s) => s, _ => "" }).await?;
    let user = if let DbValue::Str(s) = &rs[0][1] { if !s.is_empty() { decrypt_token(s).await? } else { "me".to_string() } } else { "me".to_string() };
    let body = format!("auth_token={}&value={}&comment={}", tok, val, urlencoding::encode(comment));
    let res = spin_sdk::http::send(Request::builder().method(Method::POST).uri(format!("https://www.beeminder.com/api/v1/users/{}/goals/{}/datapoints.json", user, slug)).header("content-type", "application/x-www-form-urlencoded").body(body)?).await?;
    if !(200..300).contains(&res.status().as_u16()) { return Err(anyhow::anyhow!("Push: {}", res.status())); }
    Ok(())
}

async fn send_twilio_sms(sid: &str, tok: &str, from: &str, to: &str, msg: &str) -> anyhow::Result<()> {
    let auth = base64::engine::general_purpose::STANDARD.encode(format!("{}:{}", sid, tok));
    let body = format!("From={}&To={}&Body={}", urlencoding::encode(from), urlencoding::encode(to), urlencoding::encode(msg));
    let res = spin_sdk::http::send(Request::builder().method(Method::POST).uri(format!("https://api.twilio.com/2010-04-01/Accounts/{}/Messages.json", sid)).header("Authorization", &format!("Basic {}", auth)).header("Content-Type", "application/x-www-form-urlencoded").body(body)?).await?;
    if !(200..300).contains(&res.status().as_u16()) { return Err(anyhow::anyhow!("Twilio: {}", res.status())); }
    Ok(())
}

fn local_hour_from_timezone(tz_name: &str, now: &chrono::DateTime<chrono::Utc>) -> u32 { let tz: chrono_tz::Tz = tz_name.parse().unwrap_or(chrono_tz::UTC); now.with_timezone(&tz).hour() }
fn aggregate_step_count(rs: &Vec<spin_sdk::pg::Row>) -> i32 { rs.iter().filter_map(|r| match &r[0] { DbValue::Str(s) => s.parse::<i32>().ok(), _ => None }).max().unwrap_or(0) }
fn should_dispatch(h: u32, s: i32, m: Option<u64>, _p: &NotificationPrefs) -> bool { if h < 9 || h >= 21 || s >= 2000 { false } else { m.map_or(true, |v| v >= 120) } }

async fn decrypt_token(enc_hex: &str) -> anyhow::Result<String> {
    let key_str = variables::get("master_encryption_key").await?;
    let key_bytes = hex::decode(key_str.trim())?;
    let cipher = Aes256Gcm::new_from_slice(&key_bytes)?;
    let enc_bytes = hex::decode(enc_hex.trim())?;
    if enc_bytes.len() < 12 { return Err(anyhow::anyhow!("Short")); }
    let (nonce, ct) = enc_bytes.split_at(12);
    let dec = cipher.decrypt(Nonce::from_slice(nonce), ct).map_err(|_| anyhow::anyhow!("Dec fail"))?;
    Ok(String::from_utf8(dec)?)
}

async fn encrypt_token(plain: &str) -> anyhow::Result<String> {
    let key_str = variables::get("master_encryption_key").await?;
    let key_bytes = hex::decode(key_str.trim())?;
    let cipher = Aes256Gcm::new_from_slice(&key_bytes)?;
    let mut nonce = [0u8; 12]; getrandom::getrandom(&mut nonce).map_err(|_| anyhow::anyhow!("rand"))?;
    let ct = cipher.encrypt(Nonce::from_slice(&nonce), plain.as_bytes()).map_err(|_| anyhow::anyhow!("Enc fail"))?;
    let mut comb = nonce.to_vec(); comb.extend_from_slice(&ct);
    Ok(hex::encode(comb))
}

async fn extract_user_id(auth: Option<&spin_sdk::http::HeaderValue>) -> Option<String> {
    let val = std::str::from_utf8(auth?.as_ref()).ok()?;
    if !val.starts_with("Bearer ") { return None; }
    let tok = &val[7..]; let manual = variables::get("oidc_jwks_json").await.ok()?;
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

async fn register_cloud_heartbeat(conn: &Connection, uid: &str) -> anyhow::Result<()> {
    let prov = variables::get("cloud_provider").await.unwrap_or_else(|_| "unknown".to_string());
    let role = match prov.as_str() { "akamai" => "akamai_functions", "fermyon" => "fermyon_cloud", _ => "unknown" };
    conn.execute("INSERT INTO scheduler_election (user_id, role, process_id, heartbeat) VALUES ($1, $2, $3, CURRENT_TIMESTAMP) ON CONFLICT (user_id, role) DO UPDATE SET heartbeat = EXCLUDED.heartbeat, process_id = EXCLUDED.process_id", &[ParameterValue::Str(uid.to_string()), ParameterValue::Str(role.to_string()), ParameterValue::Str(prov)]).await?;
    Ok(())
}

fn get_modality_status(role: &str, mins: u64) -> &'static str {
    match role { "leader" => if mins < 2 { "healthy" } else if mins < 5 { "degraded" } else { "offline" }, "android_client" => if mins < 20 { "healthy" } else if mins < 60 { "degraded" } else { "offline" }, "akamai_functions" => if mins < 135 { "healthy" } else if mins < 250 { "degraded" } else { "offline" }, "fermyon_cloud" => if mins < 5 { "healthy" } else if mins < 15 { "degraded" } else { "offline" }, _ => "unknown" }
}

async fn handle_weather_heuristic_get(_r: Request) -> anyhow::Result<Response<String>> { Ok(text_response(200, "Weather not implemented")?) }
#[derive(Serialize)] struct StatusResponse { status: String, message: String }
#[derive(Deserialize, Serialize, Debug)] struct Jwks { keys: Vec<JwKey> }
#[derive(Deserialize, Serialize, Debug)] struct JwKey { kid: String, kty: String, alg: String, n: String, e: String }
