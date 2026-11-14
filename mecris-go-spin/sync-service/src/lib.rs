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
/// The key that was committed to the public deploy scripts. It can never authorize again.
const BURNED_INTERNAL_KEY: &str = "test-internal-key";

/// Compare two secrets without an early exit on the first differing byte.
fn secret_eq(a: &str, b: &str) -> bool {
    a.len() == b.len() && a.bytes().zip(b.bytes()).fold(0u8, |acc, (x, y)| acc | (x ^ y)) == 0
}

fn query_param(query: Option<&str>, key: &str) -> Option<String> {
    parse_form(query?).into_iter().find(|(k, _)| k == key).map(|(_, v)| v)
}

/// Who may call the `/internal/*` trigger endpoints:
/// - a signed-in user (the Android app sends its bearer token), or
/// - a caller presenting the configured key, in the `x-internal-api-key` header or,
///   for platform cron which can only set path and query, the `key` query parameter.
/// An unset key authorizes nobody. So does the key that was once published.
fn internal_caller_ok(cfg: &str, header_key: Option<&str>, query_key: Option<&str>, signed_in_user: bool) -> bool {
    if signed_in_user { return true; }
    if cfg.is_empty() || cfg == BURNED_INTERNAL_KEY { return false; }
    header_key.map(|h| secret_eq(h, cfg)).unwrap_or(false) || query_key.map(|q| secret_eq(q, cfg)).unwrap_or(false)
}

async fn internal_request_ok(req: &Request) -> bool {
    let cfg = variables::get("internal_api_key").await.unwrap_or_default();
    let header_key = req.headers().get("x-internal-api-key").and_then(|v| v.to_str().ok());
    let query_key = query_param(req.uri().query(), "key");
    let signed_in = extract_user_id(req.headers().get("authorization")).await.is_some();
    internal_caller_ok(&cfg, header_key, query_key.as_deref(), signed_in)
}

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
    let mut path = req.uri().path().to_string();
    let method = req.method();
    
    // Fix for full URLs in path
    if path.starts_with("http") {
        if let Some(p) = path.split('/').nth(3) {
            path = format!("/{}", p);
        }
    }

    if method == &Method::OPTIONS { return Ok(Response::builder().status(204).header("access-control-allow-origin", "*").header("access-control-allow-methods", "GET, POST, PATCH, OPTIONS").header("access-control-allow-headers", "authorization, content-type, x-internal-api-key").body(String::new())?); }
    let resp = match (path.as_str(), method) {
        ("/walks", &Method::POST) => handle_walks_post(req).await?,
        ("/budget", &Method::GET) => handle_budget_get(req).await?,
        ("/languages", &Method::GET) => handle_languages_get(req).await?,
        ("/languages/multiplier", &Method::POST) => handle_multiplier_post(req).await?,
        ("/health", &Method::GET) => handle_health_get(req).await?,
        ("/heartbeat", &Method::POST) => handle_heartbeat_post(req).await?,
        ("/helix-balance/request", &Method::POST) => handle_helix_balance_request_post(req).await?,
        ("/internal/cloud-sync", &Method::POST) => handle_cloud_sync(req).await?,
        ("/aggregate-status", &Method::GET) => handle_aggregate_status_get(req).await?,
        ("/profile", &Method::POST) => handle_profile_post(req).await?,
        ("/profile", &Method::GET) => handle_profile_get(req).await?,
        ("/internal/trigger-reminders", _) => {
            if !internal_request_ok(&req).await { text_response(401, "Unauthorized")? } else { handle_trigger_reminders_post(req).await? }
        },
        ("/internal/failover-sync", _) => {
            if !internal_request_ok(&req).await { text_response(401, "Unauthorized")? } else { handle_failover_sync_post(req).await? }
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
    let walk_rs = conn.query("SELECT COUNT(*) FROM walk_inferences WHERE (start_time::TIMESTAMPTZ AT TIME ZONE 'America/New_York')::DATE = (CURRENT_TIMESTAMP AT TIME ZONE 'America/New_York')::DATE AND CAST(step_count AS INTEGER) >= 2000 AND user_id = $1", &[ParameterValue::Str(uid.clone())]).await?.collect().await?;
    let walked = !walk_rs.is_empty() && (db_to_i32(&walk_rs[0][0]) > 0);
    let lang_rows = conn.query("SELECT language_name, current_reviews, tomorrow_reviews, pump_multiplier::FLOAT8, daily_completions, beeminder_due_today FROM language_stats WHERE user_id = $1", &[ParameterValue::Str(uid.clone())]).await?.collect().await?;
    let user_rows = conn.query("SELECT vacation_mode_until::TEXT, phone_verified FROM users WHERE pocket_id_sub = $1", &[ParameterValue::Str(uid.clone())]).await?.collect().await?;
    let (vaca, phone) = if !user_rows.is_empty() { (match &user_rows[0][0] { DbValue::Str(s) if !s.is_empty() => Some(s.clone()), _ => None }, db_to_bool(&user_rows[0][1])) } else { (None, false) };
    let mut total_goals = 1; let mut goals_met = if walked { 1 } else { 0 };
    let (mut arabic_met, mut greek_met) = (false, false);
    for r in &lang_rows {
        let n = db_to_str(&r[0]);
        let (cur, tom, mult, done) = (db_to_i32(&r[1]), db_to_i32(&r[2]), db_to_f64(&r[3]), db_to_i32(&r[4]));
        // Task 000617: aggregate component verdicts honor the Beeminder due-today too.
        let (_, _, met) = effective_targets(cur, tom, mult, done, db_to_i32(&r[5]).max(0));
        if n == "ARABIC" { total_goals += 1; arabic_met = met; if met { goals_met += 1; } }
        else if n == "GREEK" { total_goals += 1; greek_met = met; if met { goals_met += 1; } }
    }
    let walk_detail_rs = conn.query("SELECT distance_meters, step_count FROM walk_inferences WHERE user_id = $1 AND (start_time::TIMESTAMPTZ AT TIME ZONE 'America/New_York')::DATE = (CURRENT_TIMESTAMP AT TIME ZONE 'America/New_York')::DATE ORDER BY start_time DESC LIMIT 1", &[ParameterValue::Str(uid.clone())]).await?.collect().await?;
    let (today_distance_miles, today_steps) = if !walk_detail_rs.is_empty() {
        let dm: f64 = match &walk_detail_rs[0][0] {
            DbValue::Str(s) => s.parse().unwrap_or(0.0),
            DbValue::Floating64(f) => *f,
            _ => 0.0,
        };
        let st: i32 = match &walk_detail_rs[0][1] {
            DbValue::Str(s) => s.parse().unwrap_or(0),
            DbValue::Int32(i) => *i,
            DbValue::Int64(i) => *i as i32,
            _ => 0,
        };
        (dm * 0.000621371, st)
    } else {
        (0.0, 0)
    };

    let budget_rs = conn.query("SELECT remaining_budget FROM budget_tracking WHERE user_id = $1 LIMIT 1", &[ParameterValue::Str(uid.clone())]).await?.collect().await?;
    let budget_remaining = if !budget_rs.is_empty() { db_to_f64(&budget_rs[0][0]) } else { 0.0 };

    #[derive(Serialize)] struct Comp { walk: bool, arabic: bool, greek: bool }
    #[derive(Serialize, Clone)] struct Mod { role: String, status: String, last_seen: String, minutes_since: u64 }
    #[derive(Serialize)] struct Pulse { modalities: Vec<Mod> }
    #[derive(Serialize)] struct AggResp { 
        score: String, 
        goals_met: i32, 
        total_goals: i32, 
        satisfied_count: i32,
        total_count: i32,
        all_clear: bool, 
        components: Comp, 
        budget_remaining: f64,
        today_distance_miles: f64,
        today_steps: i32,
        vacation_mode_until: Option<String>, 
        phone_verified: bool, 
        modalities: Option<Vec<Mod>>,
        system_pulse: Option<Pulse>
    }
    let mut mods = None;
    let mut pulse = None;
    if full {
        let p_rows = conn.query("SELECT role, heartbeat::TEXT, CAST(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - heartbeat)) / 60 AS BIGINT) AS mins FROM scheduler_election WHERE user_id = $1 OR user_id IS NULL ORDER BY heartbeat DESC", &[ParameterValue::Str(uid.clone())]).await?.collect().await?;
        let mut ms = Vec::new();
        for r in &p_rows {
            let role = db_to_str(&r[0]);
            let display = match role.as_str() { "leader" => "MCP SERVER", "android_client" => "ANDROID", "akamai_functions" => "AKAMAI", "fermyon_cloud" => "FERMYON", _ => &role };
            let mins = match &r[2] { DbValue::Int64(i) => *i as u64, _ => 9999 };
            ms.push(Mod { role: display.to_string(), status: get_modality_status(&role, mins).to_string(), last_seen: db_to_str(&r[1]), minutes_since: mins });
        }
        pulse = Some(Pulse { modalities: ms.clone() });
        mods = Some(ms);
    }
    json_response(200, &AggResp { 
        score: format!("{}/{}", goals_met, total_goals), 
        goals_met, 
        total_goals, 
        satisfied_count: goals_met,
        total_count: total_goals,
        all_clear: vaca.is_some() || goals_met >= total_goals, 
        components: Comp { walk: walked, arabic: arabic_met, greek: greek_met }, 
        budget_remaining,
        today_distance_miles,
        today_steps,
        vacation_mode_until: vaca, 
        phone_verified: phone, 
        modalities: mods,
        system_pulse: pulse
    })
}

fn clearance_days(mult: f64) -> Option<u32> {
    // Match review-pump lever config: multiplier -> clearance days
    // Multipliers are 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 10.0
    match (mult * 10.0).round() as u32 {
        10 => None,      // Maintenance: no debt clearing
        20 => Some(14),  // Steady
        30 => Some(10),  // Brisk
        40 => Some(7),   // Aggressive
        50 => Some(5),   // High Pressure
        60 => Some(3),   // Very High
        70 => Some(2),   // The Blitz
        100 => Some(1),  // System Overdrive
        _ => None,       // Unknown -> Maintenance
    }
}

fn calculate_targets(cur: i32, tom: i32, mult: f64, done: i32) -> (i32, f64, bool) {
    let rate = if mult > 0.0 { mult } else { 1.0 };
    let days = clearance_days(rate);
    
    let target = match days {
        None => tom,  // Maintenance: target = tomorrow_liability only
        Some(d) => tom + (cur / d as i32),
    };
    
    // Goal met logic matching review-pump:
    // - If no debt and no liability: vacuous success
    // - If target > 0 OR (debt > 0 AND multiplier > 1.0): done >= target
    // - Else (Maintenance with zero target): goal met only if no debt
    let goal_met = if cur == 0 && tom == 0 {
        true
    } else if target > 0 || (cur > 0 && rate > 1.0) {
        done >= target
    } else {
        cur == 0
    };
    
    (target, rate, goal_met)
}

// Task 000617 / v0.1.3: Beeminder due-today from the goal JSON's road. Python twin:
// services/beeminder_road.py — keep in lockstep. Timezone is hardcoded
// America/New_York (single-user system; operator ruling 2026-10-01).
fn road_value_today(fullroad: Option<&serde_json::Value>, daystamp: Option<i64>) -> Option<f64> {
    let day = daystamp?;
    let arr = fullroad?.as_array()?;
    let mut rows: Vec<(i64, Option<f64>, Option<f64>)> = Vec::new();
    for row in arr {
        let cells = match row.as_array() { Some(c) => c, None => continue };
        if cells.len() < 2 { continue; }
        let d = match &cells[0] {
            serde_json::Value::Number(n) => {
                if let Some(stamp) = n.as_i64() {
                    if stamp > 100_000_000 {
                        chrono::DateTime::from_timestamp(stamp, 0).map(|utc| {
                            let ny = utc.with_timezone(&chrono_tz::America::New_York);
                            ny.format("%Y%m%d").to_string().parse::<i64>().unwrap_or(stamp)
                        })
                    } else {
                        Some(stamp)
                    }
                } else {
                    None
                }
            }
            serde_json::Value::String(s) => {
                let cleaned = s.replace('-', "");
                if let Ok(stamp) = cleaned.parse::<i64>() {
                    if stamp > 100_000_000 {
                        chrono::DateTime::from_timestamp(stamp, 0).map(|utc| {
                            let ny = utc.with_timezone(&chrono_tz::America::New_York);
                            ny.format("%Y%m%d").to_string().parse::<i64>().unwrap_or(stamp)
                        })
                    } else {
                        Some(stamp)
                    }
                } else {
                    None
                }
            }
            _ => None,
        };
        let d = match d { Some(d) => d, None => continue };
        let v = cells[1].as_f64();
        let rate = cells.get(2).and_then(|c| c.as_f64());
        rows.push((d, v, rate));
    }
    if rows.is_empty() { return None; }
    rows.sort_by_key(|r| r.0);
    if day < rows[0].0 { return rows[0].1; }
    for (d, v, _rate) in &rows {
        if *d == day && v.is_some() { return *v; }
    }
    let to_date = |stamp: i64| chrono::NaiveDate::from_ymd_opt((stamp / 10000) as i32, ((stamp / 100) % 100) as u32, (stamp % 100) as u32);
    // Interpolate between bounding vertices
    for i in 0..rows.len().saturating_sub(1) {
        let (d0, v0, r0) = rows[i];
        let (d1, v1, r1) = rows[i + 1];
        if d0 <= day && day <= d1 {
            if let (Some(date0), Some(date1), Some(today_date)) = (to_date(d0), to_date(d1), to_date(day)) {
                if let (Some(r1), Some(v1)) = (r1, v1) {
                    let days_before_d1 = (date1 - today_date).num_days() as f64;
                    return Some(v1 - r1 * days_before_d1);
                }
                if let (Some(r0), Some(v0)) = (r0, v0) {
                    let days_after_d0 = (today_date - date0).num_days() as f64;
                    return Some(v0 + r0 * days_after_d0);
                }
                if let (Some(v0), Some(v1)) = (v0, v1) {
                    let total_days = (date1 - date0).num_days() as f64;
                    if total_days > 0.0 {
                        let frac = (today_date - date0).num_days() as f64 / total_days;
                        return Some(v0 + (v1 - v0) * frac);
                    }
                }
            }
        }
    }
    // Past the last row: roads continue at their final rate. Daystamps never
    // subtract linearly (20261001 - 20260930 == 71), so use real dates.
    let (last_day, last_val, last_rate) = rows[rows.len() - 1];
    if let (Some(rate), Some(last_val)) = (last_rate, last_val) {
        if let (Some(last_date), Some(today_date)) = (to_date(last_day), to_date(day)) {
            return Some(last_val + rate * (today_date - last_date).num_days() as f64);
        }
    }
    last_val
}

fn beeminder_due_today_value(yaw: Option<f64>, curval: f64, road_today: Option<f64>, safebuf: Option<i32>) -> i32 {
    if let Some(sb) = safebuf {
        if sb >= 1 {
            return 0;
        }
    }
    let (Some(road), Some(yaw)) = (road_today, yaw) else { return 0 };
    let raw = if yaw < 0.0 { curval - road } else { road - curval };
    if raw <= 0.0 { return 0; }
    // Ceil fractional demands: flooring would leave a do-less datapoint above the road.
    (raw - 1e-9).ceil() as i32
}

// Task 000617 constructive interference (Python twin: services/beeminder_road.py
// combine_pump_and_due). Beeminder due is already net of cards done (curval falls
// with each sync), so combine at the REMAINING level; the goal is met only when
// the pump is satisfied AND the Beeminder derailing obligation is dispatched.
// Returns (quota, remaining, goal_met); quota = done + remaining stays stable as
// cards are completed.
fn effective_targets(cur: i32, tom: i32, mult: f64, done: i32, beeminder_due: i32) -> (i32, i32, bool) {
    let (pump_target, _, pump_met) = calculate_targets(cur, tom, mult, done);
    let pump_remaining = (pump_target - done).max(0);
    let due = beeminder_due.max(0);
    let remaining = pump_remaining.max(due);
    (done + remaining, remaining, pump_met && due == 0)
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

// Task 588 Android hook: the app asks for a Helix balance sync; the laptop leader
// polls helix_balance_requests and runs the read+chart (the walk-sync pattern).
async fn handle_helix_balance_request_post(req: Request) -> anyhow::Result<Response<String>> {
    let uid = match extract_user_id(req.headers().get("authorization")).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let db = match variables::get("db_url").await { Ok(v) if !v.is_empty() => v, _ => variables::get("neon_db_url").await? };
    let conn = Connection::open(&db).await?;
    conn.execute("INSERT INTO helix_balance_requests (user_id, requested_at) VALUES ($1, CURRENT_TIMESTAMP) ON CONFLICT (user_id) DO UPDATE SET requested_at = CURRENT_TIMESTAMP", &[ParameterValue::Str(uid.clone())]).await?;
    // Edge-primary sync (Android+edge = the always-on server); the laptop leader
    // job is the fallback, so a failure here must leave the request queued.
    let (synced, pushed, wallet_error) = sync_helix_balance_inline(&uid, &conn).await;
    if synced {
        let _ = conn.execute("UPDATE helix_balance_requests SET processed_at = CURRENT_TIMESTAMP WHERE user_id = $1", &[ParameterValue::Str(uid.clone())]).await;
    }
    // Newest ok reading for app display + E2E confirmation; TEXT projection avoids timestamp DbValue parsing.
    let rs = conn.query("SELECT COALESCE(balance::TEXT, ''), TO_CHAR(ts AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') FROM helix_balance_log WHERE user_id = $1 AND fetch_status = 'ok' ORDER BY ts DESC LIMIT 1", &[ParameterValue::Str(uid.clone())]).await?.collect().await?;
    let (last_balance, last_ts) = if rs.is_empty() { (None, None) } else {
        let b = match &rs[0][0] { DbValue::Str(s) if !s.is_empty() => Some(s.clone()), _ => None };
        let t = match &rs[0][1] { DbValue::Str(s) => Some(s.clone()), _ => None };
        (b, t)
    };
    #[derive(Serialize)] struct HelixBalanceRequestResp { status: String, requested: bool, last_balance: Option<String>, last_reading_ts: Option<String>, pushed: bool, synced: bool, wallet_error: Option<String> }
    json_response(200, &HelixBalanceRequestResp { status: "success".to_string(), requested: true, last_balance, last_reading_ts: last_ts, pushed, synced, wallet_error })
}

// ---- Edge-primary Helix balance sync (task 588) ----------------------------
// Mirrors scripts/helix_balance_scraper.py exactly: straight copy, change-gated
// (R3), failures logged and NEVER pushed as $0, requestid scheme shared with the
// Python twin so a racing leader run dedupes at Beeminder (422 = already in).
fn helix_daystamp() -> String {
    match "US/Eastern".parse::<chrono_tz::Tz>() { Ok(tz) => chrono::Utc::now().with_timezone(&tz).format("%Y-%m-%d").to_string(), Err(_) => chrono::Utc::now().format("%Y-%m-%d").to_string() }
}

async fn fetch_helix_wallet(base: &str, token: &str) -> Result<f64, String> {
    // Mirror scripts/helix_billing.py's proven header set EXACTLY (M1 observation card):
    // Cloudflare in front of app.helix.ml 403/1010'd the bare spin client; the lever UA
    // + Accept + org_id param are what the door-trace pinned as Cloudflare-safe.
    // Every failure mode returns a typed reason (persisted to last_error, R6-adjacent).
    let org = { let o = variables::get("helix_billing_org_id").await.unwrap_or_default(); if o.is_empty() { "mecris".to_string() } else { o } };
    let req = match Request::builder().method(Method::GET).uri(format!("{}/api/v1/wallet?org_id={}", base, org)).header("authorization", format!("Bearer {}", token)).header("accept", "application/json").header("user-agent", "helix-billing-lever/1.0 (Mecris; task-588)").body(String::new()) { Ok(r) => r, Err(e) => return Err(format!("build: {e:?}")) };
    let res = match spin_sdk::http::send(req).await { Ok(r) => r, Err(e) => return Err(format!("send: {e:?}")) };
    let code = res.status().as_u16();
    let bytes = match res.into_body().collect().await { Ok(b) => b.to_bytes(), Err(e) => return Err(format!("body: {e:?}")) };
    let snip: String = String::from_utf8_lossy(&bytes.to_vec()).chars().take(200).collect();
    if !(200..300).contains(&code) { return Err(format!("status {code}: {snip}")); }
    let v: serde_json::Value = match serde_json::from_slice(&bytes.to_vec()) { Ok(v) => v, Err(e) => return Err(format!("json: {e}: {snip}")) };
    match v.get("balance").and_then(|b| b.as_f64()) { Some(b) => Ok(b), None => Err(format!("no balance key: {snip}")) }
}

/// (synced, pushed): synced=false + queued request means the laptop leader
/// fallback owns this user (token not provisioned, edge decrypt failed).
/// (synced, pushed, reason): every failure path persists its reason (last_error)
/// beside the failed row; synced=false keeps the request queued for the leader.
async fn log_helix_failure(uid: &str, conn: &Connection, reason: &str) {
    let day = helix_daystamp();
    let _ = conn.execute("INSERT INTO helix_balance_log (user_id, day, balance, delta, source, fetch_status, inflow, last_error) VALUES ($1, $2, NULL, NULL, 'api', 'failed', false, $3)", &[ParameterValue::Str(uid.to_string()), ParameterValue::Str(day), ParameterValue::Str(reason.to_string())]).await;
}

async fn sync_helix_balance_inline(uid: &str, conn: &Connection) -> (bool, bool, Option<String>) {
    let trs = match conn.query("SELECT helix_api_token_encrypted FROM users WHERE pocket_id_sub = $1", &[ParameterValue::Str(uid.to_string())]).await { Ok(q) => q.collect().await.unwrap_or_default(), Err(e) => { log_helix_failure(uid, conn, &format!("users query: {e:?}")).await; return (false, false, Some(format!("users query: {e:?}"))) } };
    let enc = match trs.first().map(|r| &r[0]) { Some(DbValue::Str(s)) if !s.is_empty() => s.clone(), _ => { log_helix_failure(uid, conn, "no provisioned token (queued for leader)").await; return (false, false, Some("no provisioned token".to_string())) } };
    let token = match decrypt_token(&enc).await { Ok(t) => t, Err(e) => { log_helix_failure(uid, conn, &format!("decrypt: {e:?}")).await; return (false, false, Some(format!("decrypt: {e:?}"))) } };
    let base = { let b = variables::get("helix_api_base_url").await.unwrap_or_default(); if b.is_empty() { "https://app.helix.ml".to_string() } else { b } };
    let day = helix_daystamp();
    let bal: f64 = match fetch_helix_wallet(&base, &token).await {
        Ok(b) => b,
        Err(e) => {
            // Unknown is never $0: log the failure with its reason, push nothing (R2/pulse R6).
            let _ = conn.execute("INSERT INTO helix_balance_log (user_id, day, balance, delta, source, fetch_status, inflow, last_error) VALUES ($1, $2, NULL, NULL, 'api', 'failed', false, $3)", &[ParameterValue::Str(uid.to_string()), ParameterValue::Str(day), ParameterValue::Str(e.clone())]).await;
            return (false, false, Some(e));
        }
    };
    let prs = match conn.query("SELECT balance::TEXT FROM helix_balance_log WHERE user_id = $1 AND fetch_status = 'ok' ORDER BY ts DESC LIMIT 1", &[ParameterValue::Str(uid.to_string())]).await { Ok(q) => q.collect().await.unwrap_or_default(), Err(_) => Vec::new() };
    let prev: Option<f64> = prs.first().and_then(|r| match &r[0] { DbValue::Str(s) => s.parse().ok(), _ => None });
    // R3 gate anchor: newest NON-NULL pushed_value ANYWHERE in history, not the
    // newest ok row — silent laps log ok rows with pushed_value NULL, so
    // anchoring there oscillates push/silent/push (v0.1.0 overnight duplicate
    // datapoints; Python twin fixed in lockstep).
    let lps = match conn.query("SELECT pushed_value::TEXT FROM helix_balance_log WHERE user_id = $1 AND pushed_value IS NOT NULL ORDER BY ts DESC LIMIT 1", &[ParameterValue::Str(uid.to_string())]).await { Ok(q) => q.collect().await.unwrap_or_default(), Err(_) => Vec::new() };
    let last_pushed: Option<f64> = lps.first().and_then(|r| match &r[0] { DbValue::Str(s) => s.parse().ok(), _ => None });
    let delta = prev.map(|p| bal - p);
    let inflow = delta.map(|d| d > 0.0).unwrap_or(false);
    // ParameterValue has no Null variant in spin-sdk 6: two INSERT shapes (delta omitted on first reading).
    let ins = match delta {
        Some(d) => conn.execute("INSERT INTO helix_balance_log (user_id, day, balance, delta, source, fetch_status, inflow) VALUES ($1, $2, $3::FLOAT8::NUMERIC, $4::FLOAT8::NUMERIC, 'api', 'ok', $5)", &[ParameterValue::Str(uid.to_string()), ParameterValue::Str(day.clone()), ParameterValue::Floating64(bal), ParameterValue::Floating64(d), ParameterValue::Boolean(inflow)]).await,
        None => conn.execute("INSERT INTO helix_balance_log (user_id, day, balance, source, fetch_status, inflow) VALUES ($1, $2, $3::FLOAT8::NUMERIC, 'api', 'ok', $4)", &[ParameterValue::Str(uid.to_string()), ParameterValue::Str(day.clone()), ParameterValue::Floating64(bal), ParameterValue::Boolean(inflow)]).await,
    };
    let _ = ins;
    let value = (bal * 100.0).round() / 100.0;
    if last_pushed.map(|lp| (lp - value).abs() < 0.005).unwrap_or(false) { return (true, false, None); } // R3: unchanged = silence
    let hhmm = chrono::Utc::now().format("%H%M").to_string();
    let rid = format!("helix-balance-{}T{}", day, hhmm);
    let comment = format!("Helix balance ${:.2} (source=api)", value);
    match push_to_beeminder_idempotent(uid, "helix-ml", value, &comment, &rid, conn).await {
        Ok(_) => {
            let _ = conn.execute("UPDATE helix_balance_log SET pushed_value = $2::FLOAT8::NUMERIC WHERE user_id = $1 AND ts = (SELECT MAX(ts) FROM helix_balance_log WHERE user_id = $1 AND fetch_status = 'ok')", &[ParameterValue::Str(uid.to_string()), ParameterValue::Floating64(value)]).await;
            (true, true, None)
        }
        Err(e) => {
            let reason = format!("push: {e:?}");
            let _ = conn.execute("UPDATE helix_balance_log SET last_error = $2 WHERE user_id = $1 AND ts = (SELECT MAX(ts) FROM helix_balance_log WHERE user_id = $1 AND fetch_status = 'ok')", &[ParameterValue::Str(uid.to_string()), ParameterValue::Str(reason.clone())]).await;
            (true, false, Some(reason))
        }
    }
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
    let rs = conn.query("SELECT language_name, current_reviews, tomorrow_reviews, next_7_days_reviews, daily_rate::FLOAT8, safebuf, derail_risk, pump_multiplier::FLOAT8, beeminder_slug, daily_completions, beeminder_due_today FROM language_stats WHERE user_id = $1 ORDER BY (beeminder_slug != '' AND beeminder_slug IS NOT NULL) DESC, language_name ASC", &[ParameterValue::Str(uid)]).await?.collect().await?;
    #[derive(Serialize)] struct LangStat { name: String, current: i32, tomorrow: i32, next_7_days: i32, daily_rate: f64, safebuf: i32, derail_risk: String, pump_multiplier: Option<f64>, daily_completions: i32, goal_met: bool, absolute_target: i32, has_goal: bool, target_flow_rate: Option<f64>, outstanding_debt: Option<i32>, beeminder_due_today: i32 }
    let mut langs = Vec::new();
    for r in &rs {
        let name = db_to_str(&r[0]);
        let cur = db_to_i32(&r[1]);
        let tom = db_to_i32(&r[2]);
        let n7 = db_to_i32(&r[3]);
        let rate = db_to_f64(&r[4]);
        let sb = db_to_i32(&r[5]);   // safebuf: days of buffer (negative = deficit)
        let risk = db_to_str(&r[6]);
        let mult = if let DbValue::Floating64(f) = r[7] { Some(f) } else { None };
        let slug = db_to_str(&r[8]);
        let done = db_to_i32(&r[9]);
        let beeminder_due = db_to_i32(&r[10]).max(0);
        
        // Task 000617: effective quota/remaining = max(pump remaining, Beeminder due);
        // goal not met while a Beeminder derailing obligation stands. Languages without
        // a Beeminder slug always have due 0, so their pump-only behavior is unchanged.
        let (effective_quota, remaining, goal_met) = effective_targets(cur, tom, mult.unwrap_or(1.0), done, beeminder_due);
        let has_goal = !slug.is_empty();
        
        langs.push(LangStat { name, current: cur, tomorrow: tom, next_7_days: n7, daily_rate: rate, safebuf: sb, derail_risk: risk, pump_multiplier: mult, daily_completions: done, goal_met, absolute_target: effective_quota, has_goal, target_flow_rate: Some(remaining as f64), outstanding_debt: Some(cur), beeminder_due_today: beeminder_due });
    }
    #[derive(Serialize)] struct LangResp { languages: Vec<LangStat> }
    json_response(200, &LangResp { languages: langs })
}

async fn handle_budget_get(req: Request) -> anyhow::Result<Response<String>> {
    let uid = match extract_user_id(req.headers().get("authorization")).await { Some(id) => id, None => return Ok(text_response(401, "Unauthorized")?) };
    let db = match variables::get("db_url").await { Ok(v) if !v.is_empty() => v, _ => variables::get("neon_db_url").await? };
    let conn = Connection::open(&db).await?;
    let rs = conn.query("SELECT remaining_budget FROM budget_tracking WHERE user_id = $1 LIMIT 1", &[ParameterValue::Str(uid)]).await?.collect().await?;
    let budget = if rs.is_empty() { 0.0 } else { db_to_f64(&rs[0][0]) };
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
    let from = variables::get("twilio_whatsapp_from").await.unwrap_or_default();
    let template = variables::get("twilio_status_template_sid").await.unwrap_or_default();
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
        match send_twilio_whatsapp_template(&sid, &_tok, &from, &ph, &template, &walk_reminder_variables(&local_time_label(&tz, &now))).await {
            // Every attempt is logged for compliance (kingdonb/mecris#167). Failed attempts also
            // count toward the walk_reminder cooldown above, so a failing channel cannot retry-storm.
            // error_msg holds only twilio_failure_summary output, encrypted like the Python logger.
            Ok(_) => { let _ = conn.execute("INSERT INTO message_log (date, user_id, type, sent_at, status, channel) VALUES (CURRENT_DATE, $1, 'walk_reminder', CURRENT_TIMESTAMP, 'sent', 'whatsapp')", &[ParameterValue::Str(uid.clone())]).await; sent += 1; }
            Err(e) => {
                let err_param = match encrypt_token(&e.to_string()).await { Ok(enc) => ParameterValue::Str(enc), Err(_) => ParameterValue::DbNull };
                let _ = conn.execute("INSERT INTO message_log (date, user_id, type, sent_at, status, channel, error_msg) VALUES (CURRENT_DATE, $1, 'walk_reminder', CURRENT_TIMESTAMP, 'failed', 'whatsapp', $2)", &[ParameterValue::Str(uid.clone()), err_param]).await;
                errors += 1;
            }
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
    let mut rb = [0u8; 4]; getrandom::fill(&mut rb).map_err(|e| anyhow::anyhow!("getrandom: {}", e))?;
    let code = format!("{:06}", (u32::from_be_bytes(rb) % 1000000));
    let hash = hex::encode(Sha256::digest(code.as_bytes()));
    let exp = (chrono::Utc::now() + chrono::Duration::minutes(15)).to_rfc3339();
    conn.execute("INSERT INTO phone_verifications (user_id, code_hash, expires_at) VALUES ($1, $2, $3::TIMESTAMPTZ) ON CONFLICT (user_id) DO UPDATE SET code_hash = EXCLUDED.code_hash, expires_at = EXCLUDED.expires_at, attempts = 0", &[ParameterValue::Str(uid.clone()), ParameterValue::Str(hash), ParameterValue::Str(exp)]).await?;
    let sid = variables::get("twilio_account_sid").await?;
    let auth = decrypt_token(&variables::get("twilio_auth_token_encrypted").await?).await?;
    let from = variables::get("twilio_whatsapp_from").await.unwrap_or_default();
    let template = variables::get("twilio_status_template_sid").await.unwrap_or_default();
    send_twilio_whatsapp_template(&sid, &auth, &from, &vr.phone_number, &template, &verification_variables(&code)).await?;
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

/// Decode an `application/x-www-form-urlencoded` body into key/value pairs.
fn parse_form(body: &str) -> Vec<(String, String)> {
    let dec = |s: &str| urlencoding::decode(&s.replace('+', " ")).map(|c| c.into_owned()).unwrap_or_default();
    body.split('&').filter(|p| !p.is_empty()).map(|p| { let mut i = p.splitn(2, '='); (dec(i.next().unwrap_or("")), dec(i.next().unwrap_or(""))) }).collect()
}

fn form_value<'a>(form: &'a [(String, String)], key: &str) -> Option<&'a str> {
    form.iter().find(|(k, _)| k == key).map(|(_, v)| v.as_str())
}

/// Bytes Twilio signs: the webhook URL followed by every POST parameter,
/// sorted by name, as name immediately followed by value.
fn twilio_signed_payload(url: &str, form: &[(String, String)]) -> String {
    let mut sorted: Vec<&(String, String)> = form.iter().collect();
    sorted.sort();
    let mut data = url.to_string();
    for (k, v) in sorted { data.push_str(k); data.push_str(v); }
    data
}

fn twilio_mac(auth_token: &str, url: &str, form: &[(String, String)]) -> hmac::Hmac<sha1::Sha1> {
    use hmac::Mac;
    let mut mac = <hmac::Hmac<sha1::Sha1> as hmac::KeyInit>::new_from_slice(auth_token.as_bytes()).expect("HMAC accepts any key length");
    mac.update(twilio_signed_payload(url, form).as_bytes());
    mac
}

/// The `X-Twilio-Signature` value Twilio would send: base64(HMAC-SHA1(auth_token, payload)).
#[allow(dead_code)]
fn twilio_signature(auth_token: &str, url: &str, form: &[(String, String)]) -> String {
    use hmac::Mac;
    base64::engine::general_purpose::STANDARD.encode(twilio_mac(auth_token, url, form).finalize().into_bytes())
}

/// True only when `header` is a valid Twilio signature for this URL and body.
/// Fails closed when the auth token or URL is not configured. Constant-time compare.
fn twilio_signature_ok(auth_token: &str, url: &str, body: &str, header: Option<&str>) -> bool {
    use hmac::Mac;
    if auth_token.is_empty() || url.is_empty() { return false; }
    let Some(sig) = header.and_then(|h| base64::engine::general_purpose::STANDARD.decode(h.trim()).ok()) else { return false };
    twilio_mac(auth_token, url, &parse_form(body)).verify_slice(&sig).is_ok()
}

/// A walk acknowledgement is a message whose text (the `Body` field only) says yes.
fn is_walk_ack(form: &[(String, String)]) -> bool {
    form_value(form, "Body").map(|b| b.to_uppercase().contains("YES")).unwrap_or(false)
}

async fn handle_twilio_webhook_post(req: Request) -> anyhow::Result<Response<String>> {
    // Twilio signs the exact URL configured in its console. Prefer the configured
    // value; fall back to the URL Spin saw for this request.
    let configured_url = variables::get("twilio_webhook_url").await.unwrap_or_default();
    let url = if configured_url.is_empty() { req.headers().get("spin-full-url").and_then(|v| v.to_str().ok()).unwrap_or("").to_string() } else { configured_url };
    let signature = req.headers().get("x-twilio-signature").and_then(|v| v.to_str().ok()).map(|s| s.to_string());
    let tok = match variables::get("twilio_auth_token_encrypted").await { Ok(enc) if !enc.is_empty() => decrypt_token(&enc).await.unwrap_or_default(), _ => String::new() };
    let body = req.into_body().collect().await.map_err(|_| anyhow::anyhow!("body"))?.to_bytes();
    let body_str = std::str::from_utf8(&body).unwrap_or("");
    if !twilio_signature_ok(&tok, &url, body_str, signature.as_deref()) {
        println!("twilio-webhook: rejected request (signature_present={})", signature.is_some());
        return Ok(text_response(403, "Forbidden")?);
    }
    let form = parse_form(body_str);
    let from_num = form_value(&form, "From").unwrap_or("").to_string();
    if is_walk_ack(&form) {
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
                    let _ = conn.execute("INSERT INTO message_log (date, user_id, type, sent_at, status, channel) VALUES (CURRENT_DATE, $1, 'walk_ack', CURRENT_TIMESTAMP, 'received', $2)", &[ParameterValue::Str(uid), ParameterValue::Str(inbound_channel(&from_num).to_string())]).await;
                }
            }
        }
    }
    Ok(Response::builder().status(200).header("content-type", "text/xml").body(r#"<?xml version="1.0" encoding="UTF-8"?><Response></Response>"#.to_string())?)
}

// Parse reviewForecast array to extract tomorrow and next_7_days values
fn parse_review_forecast(forecast: &serde_json::Value) -> (i32, i32) {
    let parse = |v: &serde_json::Value| v.get("count").and_then(|v| v.as_i64()).unwrap_or_else(|| v.as_i64().unwrap_or(0)) as i32;
    let empty_vec = vec![];
    let f = forecast.as_array().unwrap_or(&empty_vec);
    if f.is_empty() {
        return (0, 0);
    }
    let tom = parse(&f[0]);
    let n7 = f.iter().take(7).map(parse).sum();
    (tom, n7)
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
            let id = p.get("id").and_then(|v| v.as_i64().or_else(|| v.as_str().and_then(|s| s.parse::<i64>().ok()))).unwrap_or(0);
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
                let referer = format!("https://www.clozemaster.com/l/{}", slug_name);
                if let Ok(api_res) = spin_sdk::http::send(Request::builder().method(Method::GET).uri(api_url)
                    .header("User-Agent", ua)
                    .header("Cookie", &sess)
                    .header("X-CSRF-Token", fresh_csrf)
                    .header("X-Requested-With", "XMLHttpRequest")
                    .header("Accept", "*/*")
                    .header("Referer", &referer)
                    .header("Time-Zone-Offset-Hours", "-4")
                    .header("sec-ch-ua-platform", "\"macOS\"")
                    .header("sec-ch-ua", "\"Chromium\";v=\"146\", \"Not-A.Brand\";v=\"24\", \"Google Chrome\";v=\"146\"")
                    .header("sec-ch-ua-mobile", "?0")
                    .body(String::new())?).await {
                    let api_json: serde_json::Value = serde_json::from_str(&String::from_utf8(api_res.into_body().collect().await.map_err(|_| anyhow::anyhow!("body"))?.to_bytes().to_vec())?)?;
                    if let Some(f) = api_json.get("reviewForecast") {
                        let (parsed_tom, parsed_n7) = parse_review_forecast(f);
                        tom = parsed_tom;
                        n7 = parsed_n7;
                    }
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
                if let Ok(snap) = fetch_from_beeminder(uid, beem, &conn).await {
                    let (mut sb, mut risk, rate) = (snap.safebuf, snap.risk, snap.rate);
                    let (mut road_today, mut due_today) = (snap.road_today, snap.due_today);
                    if cur == 0 && tom == 0 && n7 == 0 { sb = 999; risk = "SAFE".to_string(); road_today = None; due_today = 0; }
                    // ParameterValue has no Null variant in spin-sdk 6: two UPDATE shapes.
                    match road_today {
                        Some(road) => { conn.execute("UPDATE language_stats SET safebuf = $1, derail_risk = $2, daily_rate = $3::FLOAT8::NUMERIC, beeminder_road_today = $4, beeminder_due_today = $5 WHERE user_id = $6 AND language_name = $7", &[ParameterValue::Int32(sb), ParameterValue::Str(risk.clone()), ParameterValue::Floating64(rate), ParameterValue::Int32(road as i32), ParameterValue::Int32(due_today), ParameterValue::Str(uid.to_string()), ParameterValue::Str(lang.to_uppercase())]).await?; }
                        None => { conn.execute("UPDATE language_stats SET safebuf = $1, derail_risk = $2, daily_rate = $3::FLOAT8::NUMERIC, beeminder_road_today = NULL, beeminder_due_today = $4 WHERE user_id = $5 AND language_name = $6", &[ParameterValue::Int32(sb), ParameterValue::Str(risk.clone()), ParameterValue::Floating64(rate), ParameterValue::Int32(due_today), ParameterValue::Str(uid.to_string()), ParameterValue::Str(lang.to_uppercase())]).await?; }
                    }
                }
            }
        }
    }
    Ok(())
}

/// Task 000617: what we need from the Beeminder goal JSON after a sync — the
/// classic (safebuf, risk, rate) plus the road-derived due-today. Python twin:
/// beeminder_client.BeeminderGoal (beeminder_road_today / beeminder_due_today).
struct BeeGoalSnapshot {
    safebuf: i32,
    risk: String,
    rate: f64,
    road_today: Option<f64>,
    due_today: i32,
}

fn ny_goal_daystamp() -> Option<i64> {
    let now_ny = chrono::Utc::now().with_timezone(&chrono_tz::America::New_York);
    now_ny.format("%Y%m%d").to_string().parse::<i64>().ok()
}

async fn fetch_from_beeminder(uid: &str, slug: &str, conn: &Connection) -> anyhow::Result<BeeGoalSnapshot> {
    let rs = conn.query("SELECT beeminder_token_encrypted, beeminder_user_encrypted FROM users WHERE pocket_id_sub = $1", &[ParameterValue::Str(uid.to_string())]).await?.collect().await?;
    if rs.is_empty() { return Err(anyhow::anyhow!("User")); }
    let tok = decrypt_token(match &rs[0][0] { DbValue::Str(s) => s, _ => "" }).await?;
    let user = if let DbValue::Str(s) = &rs[0][1] { if !s.is_empty() { decrypt_token(s).await? } else { "me".to_string() } } else { "me".to_string() };
    let res = spin_sdk::http::send(Request::builder().method(Method::GET).uri(format!("https://www.beeminder.com/api/v1/users/{}/goals/{}.json?auth_token={}", user, slug, tok)).body(String::new())?).await?;
    let data: serde_json::Value = serde_json::from_str(&String::from_utf8(res.into_body().collect().await.map_err(|_| anyhow::anyhow!("body"))?.to_bytes().to_vec())?)?;
    let sb = data.get("safebuf").and_then(|v| v.as_i64()).unwrap_or(0) as i32;
    let rate = data.get("rate").and_then(|v| v.as_f64()).unwrap_or(0.0);
    let risk = if sb <= 0 { "CRITICAL" } else if sb == 1 { "WARNING" } else if sb <= 3 { "CAUTION" } else { "SAFE" };
    // Task 000617: due-today from the goal's own road. The safebuf>=1 canary
    let yaw = data.get("yaw").and_then(|v| v.as_f64());
    let curval = data.get("curval").and_then(|v| v.as_f64()).unwrap_or(0.0);
    let safebump = data.get("safebump").and_then(|v| v.as_f64());
    let mut road_today = None;
    if sb == 0 {
        road_today = safebump;
    }
    if road_today.is_none() {
        road_today = road_value_today(data.get("fullroad"), ny_goal_daystamp());
    }
    if road_today.is_none() {
        road_today = safebump;
    }
    let due_today = beeminder_due_today_value(yaw, curval, road_today, Some(sb));
    if let Some(road) = road_today {
        if sb >= 1 && due_today > 0 {
            eprintln!("beeminder road canary {}: safebuf={} but due_today={} (curval={} road={} yaw={:?}) — road parse or yaw sign suspect", slug, sb, due_today, curval, road, yaw);
        }
        if let Some(delta) = data.get("delta").and_then(|v| v.as_f64()) {
            eprintln!("beeminder road cross-check {}: curval={} road_today={} api_delta={} computed_due={}", slug, curval, road, delta, due_today);
        }
    }
    Ok(BeeGoalSnapshot { safebuf: sb, risk: risk.to_string(), rate, road_today, due_today })
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

#[allow(dead_code)]
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

/// PII-free summary of a failed Twilio API call (kingdonb/mecris#167).
/// Twilio's error `message` can embed the destination number (e.g. 21211), so only
/// the HTTP status and the integer `code` field are kept; the body text never is.
fn twilio_failure_summary(http_status: u16, body: &str) -> String {
    let mut summary = format!("twilio_http_{}", http_status);
    if let Some(code) = serde_json::from_str::<serde_json::Value>(body).ok().and_then(|v| v.get("code").and_then(|c| c.as_u64())) {
        summary.push_str(&format!(" code={}", code));
    }
    summary
}

fn whatsapp_addr(number: &str) -> String {
    let n = number.trim();
    if n.starts_with("whatsapp:") { n.to_string() } else { format!("whatsapp:{}", n) }
}

fn template_variables_json(vars: &[(String, String)]) -> String {
    let map: serde_json::Map<String, serde_json::Value> = vars.iter().map(|(k, v)| (k.clone(), serde_json::Value::String(v.clone()))).collect();
    serde_json::Value::Object(map).to_string()
}

/// Form body for a Twilio Content (WhatsApp template) send. There is no freeform `Body`.
fn twilio_template_form(from: &str, to: &str, content_sid: &str, vars: &[(String, String)]) -> String {
    format!("From={}&To={}&ContentSid={}&ContentVariables={}",
        urlencoding::encode(&whatsapp_addr(from)), urlencoding::encode(&whatsapp_addr(to)),
        urlencoding::encode(content_sid), urlencoding::encode(&template_variables_json(vars)))
}

fn slots(values: [&str; 5]) -> Vec<(String, String)> {
    values.iter().enumerate().map(|(i, v)| ((i + 1).to_string(), v.to_string())).collect()
}

// Both fill mecris_status_v2 ("{{1}} is currently {{2}}. {{3}} is {{4}}. Review {{5}}."),
// with the same values the Python arm sends (services/reminder_service.py, mcp_server.py).
fn walk_reminder_variables(local_time: &str) -> Vec<(String, String)> { slots(["Daily Walk", "NOT FOUND", "Boris & Fiona", "EXPECTANT", local_time]) }
fn verification_variables(code: &str) -> Vec<(String, String)> { slots(["Identity", "PENDING", "Code", code, "Account"]) }

fn local_time_label(tz_name: &str, now: &chrono::DateTime<chrono::Utc>) -> String {
    let tz: chrono_tz::Tz = tz_name.parse().unwrap_or(chrono_tz::UTC);
    now.with_timezone(&tz).format("%I:%M %p").to_string()
}

/// Why a WhatsApp template cannot be sent with this configuration, if it cannot.
fn whatsapp_config_error(from: &str, content_sid: &str) -> Option<&'static str> {
    if from.trim().is_empty() { Some("whatsapp_sender_not_configured") }
    else if content_sid.trim().is_empty() { Some("whatsapp_template_not_configured") }
    else { None }
}

fn inbound_channel(from: &str) -> &'static str { if from.starts_with("whatsapp:") { "whatsapp" } else { "sms" } }

/// Send an approved WhatsApp template. SMS is disabled for this account, so there is no
/// SMS fallback: a missing sender or template is an error, returned before any HTTP call.
/// Errors carry only a fixed reason or twilio_failure_summary output (no PII).
async fn send_twilio_whatsapp_template(sid: &str, tok: &str, from: &str, to: &str, content_sid: &str, vars: &[(String, String)]) -> anyhow::Result<()> {
    if let Some(reason) = whatsapp_config_error(from, content_sid) { return Err(anyhow::anyhow!(reason)); }
    let auth = base64::engine::general_purpose::STANDARD.encode(format!("{}:{}", sid, tok));
    let body = twilio_template_form(from, to, content_sid, vars);
    let res = spin_sdk::http::send(Request::builder().method(Method::POST).uri(format!("https://api.twilio.com/2010-04-01/Accounts/{}/Messages.json", sid)).header("Authorization", &format!("Basic {}", auth)).header("Content-Type", "application/x-www-form-urlencoded").body(body)?).await?;
    let status = res.status().as_u16();
    if !(200..300).contains(&status) {
        let bytes = res.into_body().collect().await.map(|b| b.to_bytes()).unwrap_or_default();
        return Err(anyhow::anyhow!(twilio_failure_summary(status, &String::from_utf8_lossy(&bytes))));
    }
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
    let mut nonce = [0u8; 12]; getrandom::fill(&mut nonce).map_err(|_| anyhow::anyhow!("rand"))?;
    let ct = cipher.encrypt(Nonce::from_slice(&nonce), plain.as_bytes()).map_err(|_| anyhow::anyhow!("Enc fail"))?;
    let mut comb = nonce.to_vec(); comb.extend_from_slice(&ct);
    Ok(hex::encode(comb))
}

async fn extract_user_id(auth: Option<&spin_sdk::http::HeaderValue>) -> Option<String> {
    let val = std::str::from_utf8(auth?.as_ref()).ok()?;
    if let Ok(bypass) = variables::get("auth_bypass").await {
        if bypass == "true" {
            let token = val.strip_prefix("Bearer ").unwrap_or(val);
            if token.starts_with("TestUser ") {
                return Some(token[9..].to_string());
            }
        }
    }
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

async fn handle_weather_heuristic_get(_r: Request) -> anyhow::Result<Response<String>> {
    #[derive(Serialize)] struct WeatherResp { is_walk_appropriate: bool, conditions: String, description: String, temperature: f64, sunrise: i64, sunset: i64, is_dark: bool, now_epoch: i64, data_ts: i64, recommendation: String }
    json_response(200, &WeatherResp {
        is_walk_appropriate: true,
        conditions: "Clear".to_string(),
        description: "sunny".to_string(),
        temperature: 25.0,
        sunrise: 1717650000,
        sunset: 1717700000,
        is_dark: false,
        now_epoch: 1717680000,
        data_ts: 1717680000,
        recommendation: "Great day for a walk!".to_string()
    })
}
#[derive(Serialize)] struct StatusResponse { status: String, message: String }
#[derive(Deserialize, Serialize, Debug)] struct Jwks { keys: Vec<JwKey> }
#[derive(Deserialize, Serialize, Debug)] struct JwKey { kid: String, kty: String, alg: String, n: String, e: String }

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    // --- kingdonb/mecris#368: Spin sends WhatsApp templates, never SMS ---
    const STATUS_TEMPLATE: &str = "HX00000000000000000000000000000000";

    #[test]
    fn test_whatsapp_addr_adds_prefix_once() {
        assert_eq!(whatsapp_addr("+15005550006"), "whatsapp:+15005550006");
        assert_eq!(whatsapp_addr("whatsapp:+15005550006"), "whatsapp:+15005550006");
        assert_eq!(whatsapp_addr(" +15005550006 "), "whatsapp:+15005550006");
    }

    #[test]
    fn test_template_form_carries_content_sid_and_json_variables() {
        let vars = verification_variables("123456");
        let body = twilio_template_form("whatsapp:+15005550001", "+15005550006", STATUS_TEMPLATE, &vars);
        let form = parse_form(&body);
        assert_eq!(form_value(&form, "From"), Some("whatsapp:+15005550001"));
        assert_eq!(form_value(&form, "To"), Some("whatsapp:+15005550006"));
        assert_eq!(form_value(&form, "ContentSid"), Some(STATUS_TEMPLATE));
        assert_eq!(form_value(&form, "Body"), None, "a template send has no freeform body");
        let sent: serde_json::Value = serde_json::from_str(form_value(&form, "ContentVariables").unwrap()).unwrap();
        assert_eq!(sent, json!({"1": "Identity", "2": "PENDING", "3": "Code", "4": "123456", "5": "Account"}));
    }

    #[test]
    fn test_walk_reminder_variables_match_python_reminder_service() {
        // services/reminder_service.py fills mecris_status_v2 the same way.
        let vars = walk_reminder_variables("03:15 PM");
        let as_json = template_variables_json(&vars);
        let sent: serde_json::Value = serde_json::from_str(&as_json).unwrap();
        assert_eq!(sent, json!({"1": "Daily Walk", "2": "NOT FOUND", "3": "Boris & Fiona", "4": "EXPECTANT", "5": "03:15 PM"}));
    }

    #[test]
    fn test_local_time_label_uses_the_users_timezone() {
        let now = chrono::Utc.with_ymd_and_hms(2026, 11, 13, 20, 15, 0).unwrap();
        assert_eq!(local_time_label("America/New_York", &now), "03:15 PM");
        assert_eq!(local_time_label("not/a-zone", &now), "08:15 PM");
    }

    #[test]
    fn test_whatsapp_config_error_names_what_is_missing() {
        assert_eq!(whatsapp_config_error("whatsapp:+15005550001", STATUS_TEMPLATE), None);
        assert_eq!(whatsapp_config_error("", STATUS_TEMPLATE), Some("whatsapp_sender_not_configured"));
        assert_eq!(whatsapp_config_error("  ", STATUS_TEMPLATE), Some("whatsapp_sender_not_configured"));
        assert_eq!(whatsapp_config_error("whatsapp:+15005550001", ""), Some("whatsapp_template_not_configured"));
    }

    #[test]
    fn test_inbound_channel_follows_the_sender_address() {
        assert_eq!(inbound_channel("whatsapp:+15005550006"), "whatsapp");
        assert_eq!(inbound_channel("+15005550006"), "sms");
    }

    #[test]
    fn test_no_sms_send_path_remains() {
        // SMS is disabled for this account; a plain-body send can only fail.
        let src = include_str!("lib.rs");
        let needle = ["fn send_twilio", "_sms"].concat();
        assert!(!src.contains(&needle), "send_twilio_sms must be removed, not kept as a fallback");
    }

    // --- Internal endpoints: fail closed, no published key, callers that can actually authenticate ---
    #[test]
    fn test_internal_caller_unconfigured_key_fails_closed() {
        assert!(!internal_caller_ok("", None, None, false));
        assert!(!internal_caller_ok("", Some(""), Some(""), false));
        assert!(!internal_caller_ok("", Some("anything"), None, false));
    }

    #[test]
    fn test_internal_caller_published_key_is_burned() {
        // "test-internal-key" was committed to a public repo; it must never authorize again.
        assert!(!internal_caller_ok("test-internal-key", Some("test-internal-key"), None, false));
        assert!(!internal_caller_ok("test-internal-key", None, Some("test-internal-key"), false));
    }

    #[test]
    fn test_internal_caller_header_key() {
        assert!(internal_caller_ok("s3cret-value", Some("s3cret-value"), None, false));
        assert!(!internal_caller_ok("s3cret-value", Some("s3cret-valuX"), None, false));
        assert!(!internal_caller_ok("s3cret-value", Some("s3cret"), None, false));
        assert!(!internal_caller_ok("s3cret-value", None, None, false));
    }

    #[test]
    fn test_internal_caller_query_key_for_platform_cron() {
        // Akamai cron can only set path and query, never headers.
        assert!(internal_caller_ok("s3cret-value", None, Some("s3cret-value"), false));
        assert!(!internal_caller_ok("s3cret-value", None, Some("wrong"), false));
    }

    #[test]
    fn test_internal_caller_signed_in_user_is_allowed() {
        // The Android app triggers reminders with the user's own bearer token.
        assert!(internal_caller_ok("", None, None, true));
        assert!(internal_caller_ok("s3cret-value", Some("wrong"), None, true));
    }

    #[test]
    fn test_query_param_extracts_and_decodes() {
        assert_eq!(query_param(Some("key=abc%2B1&x=2"), "key").as_deref(), Some("abc+1"));
        assert_eq!(query_param(Some("x=2"), "key"), None);
        assert_eq!(query_param(None, "key"), None);
    }

    // --- Twilio webhook requests must carry a valid X-Twilio-Signature ---
    // Vector from Twilio's "Validating Signatures from Twilio" documentation.
    const TW_DOC_URL: &str = "https://mycompany.com/myapp.php?foo=1&bar=2";
    const TW_DOC_BODY: &str = "Digits=1234&To=%2B18005551212&From=%2B12349013030&Caller=%2B12349013030&CallSid=CA1234567890ABCDE";
    const TW_DOC_SIG: &str = "0/KCTR6DLpKmkAf8muzZqo1nDgQ=";
    const TW_HOOK_URL: &str = "https://example.test/internal/twilio-webhook";
    const TW_HOOK_BODY: &str = "To=whatsapp%3A%2B15005550001&Body=Yes+please&From=whatsapp%3A%2B15005550006";
    const TW_HOOK_SIG: &str = "hLQ9nMt/o7XZdRoX5kXYLSDNLfU=";

    #[test]
    fn test_parse_form_decodes_plus_and_percent() {
        let f = parse_form(TW_HOOK_BODY);
        assert_eq!(form_value(&f, "Body"), Some("Yes please"));
        assert_eq!(form_value(&f, "From"), Some("whatsapp:+15005550006"));
        assert_eq!(form_value(&f, "Missing"), None);
    }

    #[test]
    fn test_twilio_signature_matches_documented_vector() {
        assert_eq!(twilio_signature("12345", TW_DOC_URL, &parse_form(TW_DOC_BODY)), TW_DOC_SIG);
    }

    #[test]
    fn test_twilio_signature_ok_accepts_valid_request() {
        assert!(twilio_signature_ok("12345", TW_DOC_URL, TW_DOC_BODY, Some(TW_DOC_SIG)));
        assert!(twilio_signature_ok("test-token", TW_HOOK_URL, TW_HOOK_BODY, Some(TW_HOOK_SIG)));
    }

    #[test]
    fn test_twilio_signature_ok_rejects_missing_or_malformed_header() {
        assert!(!twilio_signature_ok("test-token", TW_HOOK_URL, TW_HOOK_BODY, None));
        assert!(!twilio_signature_ok("test-token", TW_HOOK_URL, TW_HOOK_BODY, Some("")));
        assert!(!twilio_signature_ok("test-token", TW_HOOK_URL, TW_HOOK_BODY, Some("not base64!")));
    }

    #[test]
    fn test_twilio_signature_ok_rejects_tampering() {
        let forged_from = TW_HOOK_BODY.replace("15005550006", "15005550007");
        assert!(!twilio_signature_ok("test-token", TW_HOOK_URL, &forged_from, Some(TW_HOOK_SIG)));
        assert!(!twilio_signature_ok("other-token", TW_HOOK_URL, TW_HOOK_BODY, Some(TW_HOOK_SIG)));
        assert!(!twilio_signature_ok("test-token", "https://evil.test/internal/twilio-webhook", TW_HOOK_BODY, Some(TW_HOOK_SIG)));
    }

    #[test]
    fn test_twilio_signature_ok_fails_closed_without_token_or_url() {
        // An unconfigured deployment must reject, not accept, webhook posts.
        let empty_key_sig = twilio_signature("", TW_HOOK_URL, &parse_form(TW_HOOK_BODY));
        assert!(!twilio_signature_ok("", TW_HOOK_URL, TW_HOOK_BODY, Some(&empty_key_sig)));
        assert!(!twilio_signature_ok("test-token", "", TW_HOOK_BODY, Some(TW_HOOK_SIG)));
    }

    #[test]
    fn test_walk_ack_reads_only_the_body_field() {
        assert!(is_walk_ack(&parse_form(TW_HOOK_BODY)));
        assert!(is_walk_ack(&parse_form("Body=yes")));
        assert!(!is_walk_ack(&parse_form("Body=no&ProfileName=Yesenia")));
        assert!(!is_walk_ack(&parse_form("From=%2B15005550006")));
    }

    // --- kingdonb/mecris#167: Twilio failures are summarized without PII ---
    const TWILIO_21211: &str = r#"{"code": 21211, "message": "The 'To' number +15551234567 is not a valid phone number.", "more_info": "https://www.twilio.com/docs/errors/21211", "status": 400}"#;

    #[test]
    fn test_twilio_failure_summary_keeps_status_and_code() {
        assert_eq!(twilio_failure_summary(400, TWILIO_21211), "twilio_http_400 code=21211");
    }

    #[test]
    fn test_twilio_failure_summary_never_contains_phone() {
        assert!(!twilio_failure_summary(400, TWILIO_21211).contains("5551234567"));
        assert!(!twilio_failure_summary(502, "upstream said +15551234567").contains("5551234567"));
    }

    #[test]
    fn test_twilio_failure_summary_non_json_body_is_status_only() {
        assert_eq!(twilio_failure_summary(502, "<html>Bad Gateway</html>"), "twilio_http_502");
    }

    #[test]
    fn test_twilio_failure_summary_string_code_is_dropped() {
        assert_eq!(twilio_failure_summary(400, r#"{"code": "21211 +15551234567"}"#), "twilio_http_400");
    }

    #[test]
    fn test_parse_review_forecast_with_objects() {
        let forecast = json!([{"count": 5}, {"count": 3}, {"count": 2}, {"count": 1}, {"count": 1}, {"count": 1}, {"count": 0}]);
        let (tom, n7) = parse_review_forecast(&forecast);
        assert_eq!(tom, 5);
        assert_eq!(n7, 13);
    }

    #[test]
    fn test_parse_review_forecast_with_integers() {
        let forecast = json!([4, 3, 2, 1, 1, 1, 1]);
        let (tom, n7) = parse_review_forecast(&forecast);
        assert_eq!(tom, 4);
        assert_eq!(n7, 13);
    }

    #[test]
    fn test_parse_review_forecast_empty() {
        let forecast = json!([]);
        let (tom, n7) = parse_review_forecast(&forecast);
        assert_eq!(tom, 0);
        assert_eq!(n7, 0);
    }

    #[test]
    fn test_parse_review_forecast_not_array() {
        let forecast = json!({});
        let (tom, n7) = parse_review_forecast(&forecast);
        assert_eq!(tom, 0);
        assert_eq!(n7, 0);
    }

    #[test]
    fn test_parse_review_forecast_mixed() {
        let forecast = json!([{"count": 5}, 3, {"count": 2}, 1]);
        let (tom, n7) = parse_review_forecast(&forecast);
        assert_eq!(tom, 5);
        assert_eq!(n7, 11);
    }

    // ---- Task 000617: Beeminder due-today (Python twin: services/beeminder_road.py) ----

    fn fullroad_fixture() -> serde_json::Value {
        json!([
            [20260928, 100.0, -2.0],
            [20260929, 98.0, -2.0],
            [20260930, 96.0, -2.0],
            [20261001, 94.0, -2.0],
            [20261002, 92.0, -2.0]
        ])
    }

    #[test]
    fn test_road_exact_day_match() {
        assert_eq!(road_value_today(Some(&fullroad_fixture()), Some(20261001)), Some(94.0));
    }

    #[test]
    fn test_road_missing_day_falls_back_to_last_row_rate_across_month_boundary() {
        // Road spans only through Sep 30; Oct 1 extrapolates 96 - 2*1 = 94.
        // Daystamps never subtract linearly (20261001 - 20260930 == 71) — the
        // helper must convert to real dates.
        let partial = json!([[20260928, 100.0, -2.0], [20260929, 98.0, -2.0], [20260930, 96.0, -2.0]]);
        assert_eq!(road_value_today(Some(&partial), Some(20261001)), Some(94.0));
    }

    #[test]
    fn test_road_before_first_row_returns_first_value() {
        assert_eq!(road_value_today(Some(&fullroad_fixture()), Some(20260901)), Some(100.0));
    }

    #[test]
    fn test_road_without_last_row_rate_extends_flat() {
        let flat = json!([[20260928, 100.0, -2.0], [20260929, 98.0]]);
        assert_eq!(road_value_today(Some(&flat), Some(20261001)), Some(98.0));
    }

    #[test]
    fn test_road_missing_or_malformed_returns_none() {
        assert_eq!(road_value_today(None, Some(20261001)), None);
        assert_eq!(road_value_today(Some(&json!([])), Some(20261001)), None);
        assert_eq!(road_value_today(Some(&json!([[20261001]])), Some(20261001)), None);
        assert_eq!(road_value_today(Some(&json!([["garbage", "x"]])), Some(20261001)), None);
    }

    #[test]
    fn test_road_accepts_string_and_dashed_daystamps() {
        assert_eq!(road_value_today(Some(&json!([["2026-10-01", 86.0, -4.0]])), Some(20261001)), Some(86.0));
        assert_eq!(road_value_today(Some(&json!([["20261001", 86.0, -4.0]])), Some(20261001)), Some(86.0));
    }

    #[test]
    fn test_road_none_daystamp_returns_none() {
        assert_eq!(road_value_today(Some(&fullroad_fixture()), None), None);
    }

    #[test]
    fn test_road_epoch_timestamps_and_interpolation() {
        // 1789747200 is 2026-09-18 12:00 EDT (val=397, rate=0)
        // 1791129600 is 2026-10-04 12:00 EDT (val=0, rate=-23.92)
        let epoch_road = json!([
            [1789747200, 397.0, 0.0],
            [1791129600, 0.0, -23.92]
        ]);
        // On 2026-10-01 (3 days before 2026-10-04): 0 - (-23.92 * 3) = 71.76
        let val = road_value_today(Some(&epoch_road), Some(20261001)).unwrap();
        assert_eq!((val * 100.0).round() / 100.0, 71.76);
    }

    #[test]
    fn test_due_incident_fixture_do_less() {
        // The 2026-10-01 reviewstack state: cur=257, road limit today=86, yaw=-1.
        assert_eq!(beeminder_due_today_value(Some(-1.0), 257.0, Some(86.0), None), 171);
    }

    #[test]
    fn test_due_reviewstack_live_incident_due_is_160() {
        // Reviewstack live incident: curval=246, safebump=86.04, safebuf=0, yaw=-1 -> due=160
        assert_eq!(beeminder_due_today_value(Some(-1.0), 246.0, Some(86.04), Some(0)), 160);
    }

    #[test]
    fn test_due_safebuf_ge_one_enforces_zero_due() {
        assert_eq!(beeminder_due_today_value(Some(-1.0), 246.0, Some(86.04), Some(1)), 0);
        assert_eq!(beeminder_due_today_value(Some(1.0), 50.0, Some(100.0), Some(2)), 0);
    }

    #[test]
    fn test_due_do_less_already_on_good_side_owes_zero() {
        assert_eq!(beeminder_due_today_value(Some(-1.0), 80.0, Some(86.0), None), 0);
        assert_eq!(beeminder_due_today_value(Some(-1.0), 86.0, Some(86.0), None), 0);
    }

    #[test]
    fn test_due_do_more_sign_convention() {
        assert_eq!(beeminder_due_today_value(Some(1.0), 50.0, Some(60.0), None), 10);
        assert_eq!(beeminder_due_today_value(Some(1.0), 65.0, Some(60.0), None), 0);
    }

    #[test]
    fn test_due_fractional_demand_ceils_upward() {
        // Road at 86.37: flooring would leave the do-less datapoint above the road.
        assert_eq!(beeminder_due_today_value(Some(-1.0), 257.0, Some(86.37), None), 171);
    }

    #[test]
    fn test_due_missing_yaw_or_road_fabricates_nothing() {
        assert_eq!(beeminder_due_today_value(None, 257.0, Some(86.0), None), 0);
        assert_eq!(beeminder_due_today_value(Some(-1.0), 257.0, None, None), 0);
    }

    #[test]
    fn test_effective_targets_incident_regression() {
        // 2026-10-01: cur=257, tom=0, 2x lever (14d), done=0, Beeminder due=171
        // -> remaining 171 (not the pump's 18), quota 171, goal NOT met.
        let (quota, remaining, met) = effective_targets(257, 0, 2.0, 0, 171);
        assert_eq!(remaining, 171);
        assert_eq!(quota, 171);
        assert!(!met);
    }

    #[test]
    fn test_effective_targets_pump_quota_dominates_when_larger() {
        // Quota 40 (e.g. Maintenance floor) > due 5 -> max(), not replacement.
        let (quota, remaining, met) = effective_targets(0, 40, 1.0, 0, 5);
        assert_eq!(remaining, 40);
        assert_eq!(quota, 40);
        assert!(!met);
    }

    #[test]
    fn test_effective_targets_no_due_preserves_pump_semantics() {
        // Languages without a Beeminder slug always have due 0: behavior unchanged.
        let (quota, remaining, met) = effective_targets(257, 0, 2.0, 0, 0);
        assert_eq!(remaining, 18); // 257 / 14 = 18
        assert_eq!(quota, 18);
        assert!(!met);
        // Pump met + due 0 -> met (constructive interference satisfied both).
        let (_, _, met_done) = effective_targets(257, 0, 2.0, 18, 0);
        assert!(met_done);
        // Pump met but Beeminder still due -> not met.
        let (_, _, met_beem) = effective_targets(257, 0, 2.0, 18, 171);
        assert!(!met_beem);
        assert_eq!(effective_targets(257, 0, 2.0, 18, 171).1, 171);
    }

    #[test]
    fn test_effective_targets_quota_stable_as_cards_complete() {
        // Start of day: quota 171. After 50 cards + sync (cur 207, due 121): still 171.
        let (quota0, _, _) = effective_targets(257, 0, 2.0, 0, 171);
        let (quota50, _, _) = effective_targets(207, 0, 2.0, 50, 121);
        assert_eq!(quota0, 171);
        assert_eq!(quota50, 171);
    }

    #[test]
    fn test_effective_targets_maintenance_no_goal_unchanged() {
        // Maintenance (1x) with debt but zero liability: pump says not met until the
        // debt clears; due=0 keeps that verdict (conservative case unchanged).
        let (_, _, met_debt) = effective_targets(28, 0, 1.0, 5, 0);
        assert!(!met_debt);
        let (_, _, met_clear) = effective_targets(0, 0, 1.0, 0, 0);
        assert!(met_clear); // vacuous success
    }
}
