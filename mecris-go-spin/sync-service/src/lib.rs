use std::collections::HashMap;
use serde::{Deserialize, Serialize};
use spin_sdk::{
    http::{IntoResponse, Request, Response},
    http_component,
    pg::{Connection, ParameterValue, DbValue},
    variables,
};
use spin_cron_sdk::{cron_component, Metadata};

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

use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
use jwt_simple::prelude::*;

#[derive(Deserialize, Debug, Serialize)]
struct Jwks {
    keys: Vec<JwKey>,
}

#[derive(Deserialize, Debug, Serialize)]
struct JwKey {
    kid: String,
    kty: String,
    alg: String,
    n: String,
    e: String,
}

async fn get_jwks() -> anyhow::Result<Jwks> {
    let manual_json = variables::get("oidc_jwks_json")?;
    if manual_json.is_empty() {
        return Err(anyhow::anyhow!("oidc_jwks_json variable is empty"));
    }
    let jwks: Jwks = serde_json::from_str(&manual_json)?;
    Ok(jwks)
}

#[derive(Deserialize, Debug)]
struct WalkDataSummary {
    start_time: String,
    end_time: String,
    step_count: i32,
    distance_meters: f64,
    distance_source: String,
    #[allow(dead_code)]
    confidence_score: f64,
    #[allow(dead_code)]
    gps_route_points: i32,
    #[allow(dead_code)]
    timezone: String,
}

#[derive(Serialize)]
struct StatusResponse {
    status: String,
    message: String,
}

use aes_gcm::{
    aead::{Aead, KeyInit},
    Aes256Gcm, Nonce
};

async fn decrypt_token(encrypted_hex: &str) -> anyhow::Result<String> {
    let key_str = variables::get("master_encryption_key")
        .map_err(|e| anyhow::anyhow!("Failed to get master_encryption_key: {:?}", e))?;
    let key_str = key_str.trim();
    let key_bytes = hex::decode(&key_str)
        .map_err(|e| anyhow::anyhow!("Hex decode failed for master_encryption_key (len={}): {}", key_str.len(), e))?;
    let cipher = Aes256Gcm::new_from_slice(&key_bytes)?;

    let encrypted_hex = encrypted_hex.trim();
    let encrypted_bytes = hex::decode(encrypted_hex)
        .map_err(|e| anyhow::anyhow!("Hex decode failed for encrypted data (len={}): {}", encrypted_hex.len(), e))?;
    if encrypted_bytes.len() < 12 {
        return Err(anyhow::anyhow!("Invalid encrypted token length"));
    }

    let nonce = Nonce::from_slice(&encrypted_bytes[..12]);
    let ciphertext = &encrypted_bytes[12..];

    let decrypted_bytes = cipher.decrypt(nonce, ciphertext)
        .map_err(|e| anyhow::anyhow!("Decryption failed: {:?}", e))?;

    Ok(String::from_utf8(decrypted_bytes)?)
}

async fn extract_user_id(auth_header: Option<&spin_sdk::http::HeaderValue>) -> Option<String> {
    // Allows local E2E testing without a full OAuth pipeline
    if let Ok(bypass) = variables::get("auth_bypass") {
        if bypass == "true" {
            if let Some(h) = auth_header {
                if let Ok(val) = std::str::from_utf8(h.as_ref()) {
                    if val.starts_with("TestUser ") {
                        return Some(val[9..].to_string());
                    }
                }
            }
        }
    }

    let header_val = std::str::from_utf8(auth_header?.as_ref()).ok()?;
    if !header_val.starts_with("Bearer ") {
        return None;
    }
    let token = &header_val[7..];

    let jwks = get_jwks().await.ok()?;

    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() != 3 { return None; }
    let header_bytes = URL_SAFE_NO_PAD.decode(parts[0]).ok()?;
    let header: serde_json::Value = serde_json::from_slice(&header_bytes).ok()?;
    let kid = header.get("kid")?.as_str()?;

    let key = jwks.keys.iter().find(|k| k.kid == kid)?;

    if key.kty == "RSA" && key.alg == "RS256" {
        let n_bytes = URL_SAFE_NO_PAD.decode(&key.n).ok()?;
        let e_bytes = URL_SAFE_NO_PAD.decode(&key.e).ok()?;
        let public_key = RS256PublicKey::from_components(&n_bytes, &e_bytes).ok()?;
        
        let mut options = VerificationOptions::default();
        options.time_tolerance = Some(Duration::from_mins(5));
        
        match public_key.verify_token::<NoCustomClaims>(token, Some(options)) {
            Ok(claims) => return claims.subject,
            Err(e) => {
                eprintln!("JWT VERIFY ERROR: {:?}", e);
                return None;
            }
        }
    }

    None
}

fn add_cors(resp: Response) -> Response {
    let mut builder = Response::builder();
    builder.status(*resp.status());
    
    for (name, value) in resp.headers() {
        if let Ok(v_str) = std::str::from_utf8(value.as_ref()) {
            builder.header(name, v_str);
        }
    }
    
    builder.header("access-control-allow-origin", "*");
    builder.body(resp.into_body()).build()
}

async fn register_cloud_heartbeat(connection: &Connection, user_id: &str) -> anyhow::Result<()> {
    let provider = variables::get("cloud_provider").unwrap_or_else(|_| "unknown_cloud".to_string());
    let role = match provider.as_str() {
        "akamai" => "akamai_functions",
        "fermyon" => "fermyon_cloud",
        _ => "unknown_cloud",
    };

    println!("REGISTERING HEARTBEAT: user={} role={} provider={}", user_id, role, provider);

    let query = "INSERT INTO scheduler_election (user_id, role, process_id, heartbeat) \
                 VALUES ($1, $2, $3, CURRENT_TIMESTAMP) \
                 ON CONFLICT (user_id, role) DO UPDATE SET \
                 heartbeat = EXCLUDED.heartbeat, process_id = EXCLUDED.process_id";
    
    connection.execute(query, &[
        ParameterValue::Str(user_id.to_string()),
        ParameterValue::Str(role.to_string()),
        ParameterValue::Str(provider.to_string()),
    ])?;

    Ok(())
}

#[http_component]
async fn handle_sync_service(req: Request) -> anyhow::Result<Response> {
    let path = req.path();
    let method = req.method().to_string();
    println!("REQUEST: {} {}", method, path);
    
    // Handle CORS preflight
    if req.method() == &spin_sdk::http::Method::Options {
        return Ok(Response::builder()
            .status(204)
            .header("access-control-allow-origin", "*")
            .header("access-control-allow-methods", "GET, POST, OPTIONS")
            .header("access-control-allow-headers", "authorization, content-type, x-internal-api-key")
            .build());
    }

    let response = if path == "/walks" {
        if req.method() != &spin_sdk::http::Method::Post {
            Response::builder().status(405).body("Method Not Allowed").build()
        } else {
            handle_walks_post(req).await?
        }
    } else if path == "/budget" {
        if req.method() != &spin_sdk::http::Method::Get {
            Response::builder().status(405).body("Method Not Allowed").build()
        } else {
            handle_budget_get(req).await?
        }
    } else if path == "/languages" {
        if req.method() != &spin_sdk::http::Method::Get {
            Response::builder().status(405).body("Method Not Allowed").build()
        } else {
            handle_languages_get(req).await?
        }
    } else if path == "/languages/multiplier" {
        if req.method() != &spin_sdk::http::Method::Post {
            Response::builder().status(405).body("Method Not Allowed").build()
        } else {
            handle_multiplier_post(req).await?
        }
    } else if path == "/health" {
        handle_health_get(req).await?
    } else if path == "/heartbeat" {
        if req.method() != &spin_sdk::http::Method::Post {
            Response::builder().status(405).body("Method Not Allowed").build()
        } else {
            handle_heartbeat_post(req).await?
        }
    } else if path == "/internal/cloud-sync" {
        if req.method() != &spin_sdk::http::Method::Post {
            Response::builder().status(405).body("Method Not Allowed").build()
        } else {
            handle_cloud_sync(req).await?
        }
    } else if path == "/aggregate-status" {
        if req.method() != &spin_sdk::http::Method::Get {
            Response::builder().status(405).body("Method Not Allowed").build()
        } else {
            handle_aggregate_status_get(req).await?
        }
    } else if path == "/internal/trigger-reminders" {
        if req.method() != &spin_sdk::http::Method::Post && req.method() != &spin_sdk::http::Method::Get {
            Response::builder().status(405).body("Method Not Allowed").build()
        } else {
            let configured_key = variables::get("internal_api_key").unwrap_or_default();
            let provided_key = req.header("x-internal-api-key").and_then(|v| v.as_str());
            if !internal_api_key_ok(&configured_key, provided_key) {
                Response::builder().status(401).body("Unauthorized").build()
            } else {
                handle_trigger_reminders_post(req).await?
            }
        }
    } else if path == "/internal/failover-sync" {
        // Cron sync trigger — optional API key guard (set `internal_api_key` Spin variable to enforce).
        if req.method() != &spin_sdk::http::Method::Post && req.method() != &spin_sdk::http::Method::Get {
            Response::builder().status(405).body("Method Not Allowed").build()
        } else {
            let configured_key = variables::get("internal_api_key").unwrap_or_default();
            let provided_key = req.header("x-internal-api-key").and_then(|v| v.as_str());
            if !internal_api_key_ok(&configured_key, provided_key) {
                Response::builder().status(401).body("Unauthorized").build()
            } else {
                handle_failover_sync_post(req).await?
            }
        }
    } else if path == "/internal/weather-heuristic" {
        if req.method() != &spin_sdk::http::Method::Get {
            Response::builder().status(405).body("Method Not Allowed").build()
        } else {
            handle_weather_heuristic_get(req).await?
        }
    } else if path == "/internal/request-phone-verification" {
        if req.method() != &spin_sdk::http::Method::Post {
            Response::builder().status(405).body("Method Not Allowed").build()
        } else {
            handle_request_phone_verification_post(req).await?
        }
    } else if path == "/internal/confirm-phone-verification" {
        if req.method() != &spin_sdk::http::Method::Post {
            Response::builder().status(405).body("Method Not Allowed").build()
        } else {
            handle_confirm_phone_verification_post(req).await?
        }
    } else if path == "/internal/twilio-webhook" {
        if req.method() != &spin_sdk::http::Method::Post {
            Response::builder().status(405).body("Method Not Allowed").build()
        } else {
            handle_twilio_webhook_post(req).await?
        }
    } else {
        Response::builder().status(404).body("Not Found").build()
    };

    Ok(add_cors(response))
}
fn get_modality_status_string(role: &str, mins: u64) -> &'static str {
    match role {
        "leader" => if mins < 2 { "healthy" } else if mins < 5 { "degraded" } else { "offline" },
        "android_client" => if mins < 20 { "healthy" } else if mins < 60 { "degraded" } else { "offline" },
        "akamai_functions" => if mins < 135 { "healthy" } else if mins < 250 { "degraded" } else { "offline" },
        "fermyon_cloud" => if mins < 5 { "healthy" } else if mins < 15 { "degraded" } else { "offline" },
        _ => "unknown",
    }
}

async fn handle_aggregate_status_get(req: Request) -> anyhow::Result<Response> {
    let auth_header = req.header("authorization");
    let user_id = match extract_user_id(auth_header).await {
        Some(id) => id,
        None => return Ok(Response::builder().status(401).body("Unauthorized").build()),
    };

    // Manual query param check to avoid 'url' crate dependency
    let full = req.uri().contains("full=true");

    let db_url = variables::get("db_url").or_else(|_| variables::get("neon_db_url"))?;
    let connection = Connection::open(&db_url)?;

    // 1. Check Walk Status (>= 2000 steps today US/Eastern)
    let walk_query = r#"
        SELECT COUNT(*) FROM walk_inferences 
        WHERE (start_time::TIMESTAMPTZ AT TIME ZONE 'US/Eastern')::DATE = (CURRENT_TIMESTAMP AT TIME ZONE 'US/Eastern')::DATE
        AND CAST(step_count AS INTEGER) >= 2000
        AND user_id = $1
    "#;
    let walk_rs = connection.query(walk_query, &[ParameterValue::Str(user_id.clone())])?;
    let has_walked = if !walk_rs.rows.is_empty() {
        match &walk_rs.rows[0][0] { DbValue::Int64(i) => *i > 0, _ => false }
    } else {
        false
    };

    // 2. Check Language Stats
    let lang_query = "SELECT language_name, current_reviews, tomorrow_reviews, pump_multiplier::FLOAT8, daily_completions FROM language_stats WHERE user_id = $1";
    let lang_rs = connection.query(lang_query, &[ParameterValue::Str(user_id.clone())])?;

    // 3. Fetch vacation_mode_until and phone_verified
    let user_query = "SELECT vacation_mode_until::TEXT, phone_verified FROM users WHERE pocket_id_sub = $1";
    let user_rs = connection.query(user_query, &[ParameterValue::Str(user_id.clone())])?;
    let (vacation_mode_until, phone_verified) = if !user_rs.rows.is_empty() {
        let v = match &user_rs.rows[0][0] { DbValue::Str(s) => Some(s.clone()), _ => None };
        let p = match &user_rs.rows[0][1] { DbValue::Boolean(b) => *b, _ => false };
        (v, p)
    } else {
        (None, false)
    };

    let mut goals_met = 0;
    let mut total_goals = 1; // Base goal: Walk
    if has_walked { goals_met += 1; }

    let mut arabic_met = false;
    let mut greek_met = false;

    for row in lang_rs.rows {
        let name = match &row[0] { DbValue::Str(s) => s.to_uppercase(), _ => "".to_string() };
        let current = match &row[1] { DbValue::Int32(i) => *i, _ => 0 };
        let tomorrow = match &row[2] { DbValue::Int32(i) => *i, _ => 0 };
        let multiplier = match &row[3] { DbValue::Floating64(f) => *f, _ => 1.0 };
        let daily_done = match &row[4] { DbValue::Int32(i) => *i, _ => 0 };

        if name == "ARABIC" || name == "GREEK" {
            total_goals += 1;
            
            // Ported ReviewPump target logic
            let clearance_days = match multiplier as i32 {
                2 => Some(14.0),
                3 => Some(10.0),
                4 => Some(7.0),
                5 => Some(5.0),
                6 => Some(3.0),
                7 => Some(2.0),
                10 => Some(1.0),
                _ => None,
            };

            let target = match clearance_days {
                None => tomorrow,
                Some(days) => {
                    let backlog_portion = current as f64 / days;
                    (tomorrow as f64 + backlog_portion) as i32
                }
            };

            let is_met = if target > 0 || (current > 0 && multiplier > 1.0) {
                daily_done >= target
            } else {
                current == 0
            };

            if is_met { goals_met += 1; }
            if name == "ARABIC" { arabic_met = is_met; }
            if name == "GREEK" { greek_met = is_met; }
        }
    }

    #[derive(Serialize)]
    struct ModalityStatus {
        role: String,
        status: String, // healthy, degraded, offline
        last_seen: String,
        minutes_since: u64,
    }

    #[derive(Serialize)]
    struct SystemPulse {
        modalities: Vec<ModalityStatus>,
    }

    #[derive(Serialize)]
    struct AggregateComponents {
        walk: bool,
        arabic: bool,
        greek: bool,
    }

    #[derive(Serialize)]
    struct AggregateResponse {
        score: String,
        goals_met: i32,
        total_goals: i32,
        all_clear: bool,
        components: AggregateComponents,
        vacation_mode_until: Option<String>,
        phone_verified: bool,
        system_pulse: Option<SystemPulse>,
    }

    let mut system_pulse = None;
    if full {
        let pulse_query = "SELECT role, heartbeat::TEXT, EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - heartbeat)) / 60 AS minutes_since \
                           FROM scheduler_election WHERE user_id = $1";
        let pulse_rs = connection.query(pulse_query, &[ParameterValue::Str(user_id.clone())])?;
        
        let mut modalities = Vec::new();
        for row in pulse_rs.rows {
            let role = match &row[0] { DbValue::Str(s) => s.clone(), _ => continue };
            let last_seen = match &row[1] { DbValue::Str(s) => s.clone(), _ => "never".to_string() };
            let mins = match &row[2] { 
                DbValue::Floating64(f) => *f as u64,
                DbValue::Str(s) => s.parse::<f64>().ok().map(|f| f as u64).unwrap_or(9999),
                _ => 9999 
            };

            let status = get_modality_status_string(&role, mins);

            modalities.push(ModalityStatus {
                role,
                status: status.to_string(),
                last_seen,
                minutes_since: mins,
            });
        }
        system_pulse = Some(SystemPulse { modalities });
    }

    let resp = AggregateResponse {
        score: format!("{}/{}", goals_met, total_goals),
        goals_met,
        total_goals,
        all_clear: goals_met == total_goals,
        components: AggregateComponents {
            walk: has_walked,
            arabic: arabic_met,
            greek: greek_met,
        },
        vacation_mode_until,
        phone_verified,
        system_pulse,
    };

    Ok(Response::builder()
        .status(200)
        .header("content-type", "application/json")
        .body(serde_json::to_string(&resp).unwrap())
        .build())
}

/// Returns true when the sync request should be forwarded to the user's Home Server
/// rather than handled locally by Spin. Delegation is skipped for local/loopback URLs
/// to prevent infinite loops when the bot is running on localhost.
fn should_delegate(delegation_enabled: bool, mcp_server_url: &str) -> bool {
    delegation_enabled
        && !mcp_server_url.is_empty()
        && !mcp_server_url.contains("localhost")
        && !mcp_server_url.contains("127.0.0.1")
}

/// Extract a review count from a Clozemaster forecast entry.
/// Entries may be `{ "count": N }` objects or raw integers, depending on API version.
fn parse_forecast_count(v: &serde_json::Value) -> i32 {
    v.get("count")
        .and_then(|c| c.as_i64())
        .unwrap_or_else(|| v.as_i64().unwrap_or(0)) as i32
}

/// Convert raw Clozemaster points into an estimated card count for ARABIC.
/// Heuristic: 1 card ≈ 12 points (derived empirically from scoring data).
fn arabic_completions(points_today: i32) -> i32 {
    (points_today as f64 / 12.0) as i32
}

async fn handle_cloud_sync(req: Request) -> anyhow::Result<Response> {
    let auth_header = req.header("authorization").cloned();
    let user_id = match extract_user_id(auth_header.as_ref()).await {
        Some(id) => id,
        None => return Ok(Response::builder().status(401).body("Unauthorized").build()),
    };

    let db_url = variables::get("db_url")
        .or_else(|_| variables::get("neon_db_url"))
        .map_err(|e| anyhow::anyhow!("db_url/neon_db_url fetch failed: {:?}", e))?;
    let connection = Connection::open(&db_url)?;

    // Register heartbeat for this cloud instance
    let _ = register_cloud_heartbeat(&connection, &user_id).await;

    // Check if delegation is enabled via Spin variable (default: false)
    let delegation_enabled = variables::get("delegation_enabled").unwrap_or_else(|_| "false".to_string()) == "true";

    if delegation_enabled {
        // Check if Home Server (Python MCP) is active
        let mcp_active_query = "SELECT mcp_server_url FROM users WHERE pocket_id_sub = $1";
        let mcp_rows = connection.query(mcp_active_query, &[ParameterValue::Str(user_id.clone())])?;
        let mcp_server_url = match mcp_rows.rows.first() {
            Some(row) => match &row[0] { DbValue::Str(s) => s.clone(), _ => String::new() },
            None => String::new(),
        };

        if should_delegate(delegation_enabled, &mcp_server_url) {
            // Home server URL is likely public/reachable — attempt delegation
            let sync_trigger_url = format!("{}/internal/cloud-sync", mcp_server_url.trim_end_matches('/'));
            
            let resp = StatusResponse { 
                status: "accepted".to_string(), 
                message: "Home Server is online. Delegating cloud sync to Home.".to_string() 
            };
            
            let trigger_req = Request::post(sync_trigger_url, "")
                .header("Authorization", auth_header.unwrap().as_str().unwrap())
                .build();
            let _ = spin_sdk::http::send::<Request, Response>(trigger_req).await;

            return Ok(Response::builder()
                .status(202)
                .header("content-type", "application/json")
                .body(serde_json::to_string(&resp).unwrap())
                .build());
        }
    }

    // Fallback: Spin does the heavy lifting (Parallelized scrapper)
    match run_clozemaster_scraper(&db_url, &user_id).await {
        Ok(_) => {
            // After successfully syncing Clozemaster, also evaluate and trigger any pending text reminders.
            // We pass a dummy request because the handler currently doesn't use the request body.
            let dummy_req = Request::post("/internal/trigger-reminders", "").build();
            let _ = handle_trigger_reminders_post(dummy_req).await;

            let resp = StatusResponse { status: "success".to_string(), message: "Cloud sync complete (Autonomous)".to_string() };
            Ok(Response::builder().status(200).header("content-type", "application/json").body(serde_json::to_string(&resp).unwrap()).build())
        }
        Err(e) => {
            let error_msg = format!("Autonomous sync failed: {}", e);
            eprintln!("{}", error_msg);
            let resp = StatusResponse { status: "error".to_string(), message: error_msg };
            Ok(Response::builder().status(500).header("content-type", "application/json").body(serde_json::to_string(&resp).unwrap()).build())
        }
    }
}
async fn run_clozemaster_scraper(db_url: &str, user_id: &str) -> anyhow::Result<()> {
    // ENFORCE ENCRYPTION SECURITY
    let master_key = variables::get("master_encryption_key")
        .map_err(|_| anyhow::anyhow!("MASTER_ENCRYPTION_KEY missing from environment"))?;
    if master_key.is_empty() {
        return Err(anyhow::anyhow!("MASTER_ENCRYPTION_KEY is empty; encryption is required"));
    }

    let connection = Connection::open(db_url)?;
    
    // Fetch encrypted Clozemaster credentials from Neon
    let query = "SELECT clozemaster_email_encrypted, clozemaster_password_encrypted FROM users WHERE pocket_id_sub = $1";
    let row_set = connection.query(query, &[ParameterValue::Str(user_id.to_string())])?;
    if row_set.rows.is_empty() {
        return Err(anyhow::anyhow!("User not found in database"));
    }

    let email_enc = match &row_set.rows[0][0] {
        DbValue::Str(s) if !s.is_empty() => s.clone(),
        _ => return Err(anyhow::anyhow!("Clozemaster email not set for user")),
    };
    
    let password_enc = match &row_set.rows[0][1] {
        DbValue::Str(s) if !s.is_empty() => s.clone(),
        _ => return Err(anyhow::anyhow!("Clozemaster password not set for user")),
    };

    let email = decrypt_token(&email_enc).await?;
    let password = decrypt_token(&password_enc).await?;

    let user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36";
    
    // 1. Fetch login page to get CSRF token and session cookie
    let login_page_url = "https://www.clozemaster.com/login";
    let req = Request::get(login_page_url)
        .header("User-Agent", user_agent)
        .build();
    let res: Response = spin_sdk::http::send(req).await?;
    
    let body_str = std::str::from_utf8(res.body()).unwrap_or("");
    
    // Extract CSRF token using regex
    let re = regex::Regex::new(r#"name="authenticity_token" value="([^"]*)""#)?;
    let csrf_token = re.captures(body_str)
        .and_then(|cap| cap.get(1))
        .map(|m| m.as_str())
        .ok_or_else(|| anyhow::anyhow!("Could not find CSRF token"))?;

    let cookies = res.header("set-cookie").and_then(|v| v.as_str()).unwrap_or("");
    let session_cookie = cookies.split(';').next().unwrap_or("");

    // 2. POST login credentials
    let login_body = format!(
        "user%5Blogin%5D={}&user%5Bpassword%5D={}&authenticity_token={}&commit=Log+In", 
        urlencoding::encode(&email), 
        urlencoding::encode(&password),
        urlencoding::encode(csrf_token)
    );
    
    let req = Request::post(login_page_url, login_body)
        .header("content-type", "application/x-www-form-urlencoded")
        .header("User-Agent", user_agent)
        .header("Cookie", session_cookie)
        .build();
    let res: Response = spin_sdk::http::send(req).await?;
    
    if !(200..400).contains(res.status()) {
        return Err(anyhow::anyhow!("Clozemaster login failed with status {}", res.status()));
    }

    // Use cookie from login response if provided, otherwise keep old one
    let cookies = res.header("set-cookie").and_then(|v| v.as_str()).unwrap_or(session_cookie);
    let session_cookie = cookies.split(';').next().unwrap_or(session_cookie);

    // 3. Fetch dashboard to get React props
    let dashboard_url = "https://www.clozemaster.com/dashboard";
    let req = Request::get(dashboard_url)
        .header("User-Agent", user_agent)
        .header("Cookie", session_cookie)
        .build();
    let res: Response = spin_sdk::http::send(req).await?;
    
    // Allow 302 if it's redirecting to the dashboard itself
    if !(200..300).contains(res.status()) && *res.status() != 302 {
        return Err(anyhow::anyhow!("Clozemaster dashboard fetch failed with status {}", res.status()));
    }

    let mut body_str = std::str::from_utf8(res.body()).unwrap_or("").to_string();

    // If it's a redirect, we might need to follow it once to get the final page
    if *res.status() == 302 {
        if let Some(location) = res.header("location").and_then(|v| v.as_str()) {
            let final_url = if location.starts_with('/') { format!("https://www.clozemaster.com{}", location) } else { location.to_string() };
            let req = Request::get(final_url)
                .header("User-Agent", user_agent)
                .header("Cookie", session_cookie)
                .build();
            let res: Response = spin_sdk::http::send(req).await?;
            body_str = std::str::from_utf8(res.body()).unwrap_or("").to_string();
        }
    }
    
    // Extract React props from data-react-props
    let re = regex::Regex::new(r#"data-react-props="([^"]*)""#)?;
    let props_escaped = re.captures(&body_str)
        .and_then(|cap| cap.get(1))
        .map(|m| m.as_str())
        .ok_or_else(|| anyhow::anyhow!("Could not find data-react-props"))?;
    
    // Extract fresh CSRF token from dashboard meta tag
    let csrf_re = regex::Regex::new(r#"<meta name="csrf-token" content="([^"]*)""#)?;
    let fresh_csrf = csrf_re.captures(&body_str)
        .and_then(|cap| cap.get(1))
        .map(|m| m.as_str())
        .unwrap_or(csrf_token);
    
    let props_json = html_escape::decode_html_entities(props_escaped);
    let props: serde_json::Value = serde_json::from_str(&props_json)?;
    
    if let Some(pairings) = props.get("languagePairings").and_then(|l| l.as_array()) {
        let mut futures = Vec::new();

        for pair in pairings {
            let lp_id = pair.get("id").and_then(|id| id.as_i64()).unwrap_or(0);
            let name = pair.get("slug").and_then(|n| n.as_str()).unwrap_or("UNKNOWN").to_string();
            let current = pair.get("numReadyForReview").and_then(|c| c.as_i64()).unwrap_or(0) as i32;
            let points_total = pair.get("score").and_then(|c| c.as_i64()).unwrap_or(0) as i32;
            let points_today = pair.get("numPointsToday").and_then(|c| c.as_i64()).unwrap_or(0) as i32;
            
            let user_id = user_id.to_string();
            let db_url = db_url.to_string();
            let session_cookie = session_cookie.to_string();
            let fresh_csrf = fresh_csrf.to_string();

            // We use a small internal async block/function to process each language
            futures.push(async move {
                let (lang_name, beeminder_slug) = match name.as_str() {
                    "ara-eng" => ("ARABIC", "reviewstack"),
                    "ell-eng" => ("GREEK", ""),
                    _ => (name.as_str(), ""),
                };

                let mut tomorrow = 0;
                let mut next_7 = 0;
                
                // 1. Fetch Tomorrow/7-day forecast from private API
                if lp_id > 0 {
                    let api_url = format!("https://www.clozemaster.com/api/v1/lp/{}/more-stats", lp_id);
                    let api_req = Request::get(api_url)
                        .header("User-Agent", user_agent)
                        .header("Cookie", &session_cookie)
                        .header("X-CSRF-Token", &fresh_csrf)
                        .header("Referer", &format!("https://www.clozemaster.com/l/{}", name))
                        .header("X-Requested-With", "XMLHttpRequest")
                        .header("Time-Zone-Offset-Hours", "-4")
                        .build();
                    
                    if let Ok(api_res) = spin_sdk::http::send::<Request, Response>(api_req).await {
                        if (200..300).contains(api_res.status()) {
                            if let Ok(api_json) = serde_json::from_slice::<serde_json::Value>(api_res.body()) {
                                if let Some(forecast) = api_json.get("reviewForecast").and_then(|f| f.as_array()) {
                                    if !forecast.is_empty() {
                                                        tomorrow = parse_forecast_count(&forecast[0]);
                                        next_7 = forecast.iter().take(7).map(parse_forecast_count).sum();
                                    }
                                }
                            }
                        }
                    }
                }

                // 2. Database Update & Beeminder Sync
                if let Ok(connection) = Connection::open(&db_url) {
                    let select_query = "SELECT current_reviews, beeminder_last_sync::TEXT FROM language_stats WHERE user_id = $1 AND language_name = $2";
                    let row_set = connection.query(select_query, &[
                        ParameterValue::Str(user_id.clone()),
                        ParameterValue::Str(lang_name.to_uppercase())
                    ]).ok();

                    let mut prev_reviews = -1;
                    let mut beeminder_last_sync_str = String::new();

                    if let Some(rs) = row_set {
                        if !rs.rows.is_empty() {
                            prev_reviews = match &rs.rows[0][0] { DbValue::Int32(i) => *i, _ => -1 };
                            beeminder_last_sync_str = match &rs.rows[0][1] { DbValue::Str(s) => s.clone(), _ => String::new() };
                        }
                    }

                    let mut completions = points_today;
                    if lang_name == "ARABIC" {
                        completions = arabic_completions(points_today);
                    }
                    
                    let query = "INSERT INTO language_stats (user_id, language_name, current_reviews, tomorrow_reviews, next_7_days_reviews, beeminder_slug, daily_completions, last_points, total_points, last_updated) 
                                 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, CURRENT_TIMESTAMP) 
                                 ON CONFLICT (user_id, language_name) DO UPDATE SET 
                                 current_reviews = EXCLUDED.current_reviews, 
                                 tomorrow_reviews = EXCLUDED.tomorrow_reviews,
                                 next_7_days_reviews = EXCLUDED.next_7_days_reviews,
                                 beeminder_slug = EXCLUDED.beeminder_slug,
                                 daily_completions = EXCLUDED.daily_completions,
                                 last_points = EXCLUDED.last_points,
                                 total_points = EXCLUDED.total_points,
                                 last_updated = CURRENT_TIMESTAMP";
                    let _ = connection.execute(query, &[
                        ParameterValue::Str(user_id.clone()),
                        ParameterValue::Str(lang_name.to_uppercase()), 
                        ParameterValue::Int32(current),
                        ParameterValue::Int32(tomorrow),
                        ParameterValue::Int32(next_7),
                        ParameterValue::Str(beeminder_slug.to_string()),
                        ParameterValue::Int32(completions),
                        ParameterValue::Int32(points_total),
                        ParameterValue::Int32(points_total)
                    ]);

                    if !beeminder_slug.is_empty() {
                        let today_ny = chrono::Utc::now().with_timezone(&chrono_tz::America::New_York).format("%Y-%m-%d").to_string();
                        let is_new_day = !beeminder_last_sync_str.contains(&today_ny);
                        
                        if current != prev_reviews || is_new_day {
                            let now = chrono::Local::now().format("%Y-%m-%d %H:%M").to_string();
                            let mut comment = format!("Auto-synced from Clozemaster (Cloud) at {}", now);
                            if tomorrow > 0 { comment += &format!(" | Tomorrow: {}", tomorrow); }
                            if next_7 > 0 { comment += &format!(" | 7-day: {}", next_7); }
                            
                            if let Ok(_) = push_to_beeminder(&user_id, beeminder_slug, current as f64, &comment, &connection).await {
                                let _ = connection.execute(
                                    "UPDATE language_stats SET beeminder_last_sync = CURRENT_TIMESTAMP WHERE user_id = $1 AND language_name = $2",
                                    &[ParameterValue::Str(user_id.clone()), ParameterValue::Str(lang_name.to_uppercase())]
                                );
                            }
                        }

                        if let Ok((mut safebuf, mut risk, rate)) = fetch_from_beeminder(&user_id, beeminder_slug, &connection).await {
                            if current == 0 && tomorrow == 0 && next_7 == 0 {
                                safebuf = 999;
                                risk = "SAFE".to_string();
                            }
                            let _ = connection.execute(
                                "UPDATE language_stats SET safebuf = $1, derail_risk = $2, daily_rate = $3::FLOAT8::NUMERIC WHERE user_id = $4 AND language_name = $5",
                                &[
                                    ParameterValue::Int32(safebuf),
                                    ParameterValue::Str(risk),
                                    ParameterValue::Floating64(rate),
                                    ParameterValue::Str(user_id.clone()),
                                    ParameterValue::Str(lang_name.to_uppercase())
                                ]
                            );
                        }
                    }
                }
            });
        }
        futures::future::join_all(futures).await;
    }
    Ok(())
}

async fn fetch_from_beeminder(user_id: &str, slug: &str, connection: &Connection) -> anyhow::Result<(i32, String, f64)> {
    // 1. Fetch encrypted token and user
    let query = "SELECT beeminder_token_encrypted, beeminder_user_encrypted FROM users WHERE pocket_id_sub = $1";
    let row_set = connection.query(query, &[ParameterValue::Str(user_id.to_string())])?;
    if row_set.rows.is_empty() {
        return Err(anyhow::anyhow!("User not found"));
    }
    
    let token_raw = match &row_set.rows[0][0] { DbValue::Str(s) => s.clone(), _ => return Err(anyhow::anyhow!("No token")) };
    let enc_beeminder_user = match &row_set.rows[0][1] { DbValue::Str(s) if !s.is_empty() => s.clone(), _ => "".to_string() };

    let master_key = variables::get("master_encryption_key")
        .map_err(|_| anyhow::anyhow!("MASTER_ENCRYPTION_KEY missing from environment"))?;
    if master_key.is_empty() {
        return Err(anyhow::anyhow!("MASTER_ENCRYPTION_KEY is empty; encryption is required"));
    }

    let token = decrypt_token(&token_raw).await?;
    let beeminder_user = if !enc_beeminder_user.is_empty() {
        decrypt_token(&enc_beeminder_user).await.unwrap_or_else(|_| "me".to_string())
    } else {
        "me".to_string()
    };

    // 2. GET goal details
    let url = format!("https://www.beeminder.com/api/v1/users/{}/goals/{}.json?auth_token={}", beeminder_user, slug, token);
    let req = Request::get(url).build();
    let res: Response = spin_sdk::http::send(req).await?;
    
    if !(200..300).contains(res.status()) {
        return Err(anyhow::anyhow!("Beeminder fetch failed: {}", res.status()));
    }

    let body_bytes = res.body();
    let goal_data: serde_json::Value = serde_json::from_slice(body_bytes)?;

    let safebuf = goal_data.get("safebuf").and_then(|v| v.as_i64()).unwrap_or(0) as i32;
    let rate = goal_data.get("rate").and_then(|v| v.as_f64()).unwrap_or(0.0);
    
    // Classify risk (mimic Python BeeminderClient logic)
    let risk = if safebuf <= 0 { "CRITICAL" } 
               else if safebuf == 1 { "WARNING" }
               else if safebuf <= 3 { "CAUTION" }
               else { "SAFE" };

    Ok((safebuf, risk.to_string(), rate))
}

async fn push_to_beeminder(user_id: &str, slug: &str, value: f64, comment: &str, connection: &Connection) -> anyhow::Result<()> {
    // Fetch user's Beeminder token (encrypted) from Neon
    let query = "SELECT beeminder_token_encrypted, beeminder_user_encrypted FROM users WHERE pocket_id_sub = $1";
    let row_set = connection.query(query, &[ParameterValue::Str(user_id.to_string())])?;
    if row_set.rows.is_empty() {
        return Err(anyhow::anyhow!("User not found for Beeminder sync"));
    }
    
    let encrypted_token = match &row_set.rows[0][0] {
        DbValue::Str(s) => s.clone(),
        _ => return Err(anyhow::anyhow!("Token missing")),
    };
    
    let enc_beeminder_user = match &row_set.rows[0][1] {
        DbValue::Str(s) if !s.is_empty() => s.clone(),
        _ => "".to_string(),
    };

    let master_key = variables::get("master_encryption_key")
        .map_err(|_| anyhow::anyhow!("MASTER_ENCRYPTION_KEY missing from environment"))?;
    if master_key.is_empty() {
        return Err(anyhow::anyhow!("MASTER_ENCRYPTION_KEY is empty; encryption is required"));
    }

    let token = decrypt_token(&encrypted_token).await?;
    let beeminder_user = if !enc_beeminder_user.is_empty() {
        decrypt_token(&enc_beeminder_user).await.unwrap_or_else(|_| "me".to_string())
    } else {
        "me".to_string()
    };

    let url = format!("https://www.beeminder.com/api/v1/users/{}/goals/{}/datapoints.json", beeminder_user, slug);
    let body = format!("auth_token={}&value={}&comment={}", 
        token, value, urlencoding::encode(comment));
    
    let req = Request::post(url, body)
        .header("content-type", "application/x-www-form-urlencoded")
        .build();
    
    let res: Response = spin_sdk::http::send(req).await?;
    if !(200..300).contains(res.status()) {
        let error_msg = format!("Beeminder push failed for {}: {} - Value: {}", slug, res.status(), value);
        eprintln!("{}", error_msg);
        return Err(anyhow::anyhow!(error_msg));
    }
    
    Ok(())
}

async fn handle_health_get(req: Request) -> anyhow::Result<Response> {
    let auth_header = req.header("authorization");
    let user_id = match extract_user_id(auth_header).await {
        Some(id) => id,
        None => return Ok(Response::builder().status(401).body("Unauthorized").build()),
    };

    let db_url = variables::get("db_url").or_else(|_| variables::get("neon_db_url"))?;
    let connection = Connection::open(&db_url)?;

    // Register heartbeat for this cloud instance
    let _ = register_cloud_heartbeat(&connection, &user_id).await;
    
    #[derive(Serialize)]
    struct HealthResponse {
        status: String,
        home_server_active: bool,
        leader_pid: String,
        last_seen: String,
    }

    let mut home_active = false;
    let mut pid = "none".to_string();
    let mut last_seen = "never".to_string();

    let query = "SELECT (heartbeat > CURRENT_TIMESTAMP - INTERVAL '90 seconds') as is_fresh, heartbeat::TEXT, process_id FROM scheduler_election WHERE user_id = $1 AND role = 'leader'";
    let row_set = connection.query(query, &[ParameterValue::Str(user_id)])?;

    if !row_set.rows.is_empty() {
        home_active = match &row_set.rows[0][0] { DbValue::Boolean(b) => *b, _ => false };
        last_seen = match &row_set.rows[0][1] { DbValue::Str(s) => s.clone(), _ => "unknown".to_string() };
        pid = match &row_set.rows[0][2] { DbValue::Str(s) => s.clone(), _ => "unknown".to_string() };
    }

    let resp = HealthResponse {
        status: "ok".to_string(),
        home_server_active: home_active,
        leader_pid: pid,
        last_seen: last_seen,
    };

    Ok(Response::builder()
        .status(200)
        .header("content-type", "application/json")
        .body(serde_json::to_string(&resp).unwrap())
        .build())
}

async fn handle_heartbeat_post(req: Request) -> anyhow::Result<Response> {
    let auth_header = req.header("authorization");
    let user_id = match extract_user_id(auth_header).await {
        Some(id) => id,
        None => return Ok(Response::builder().status(401).body("Unauthorized").build()),
    };

    let body_bytes = req.into_body();
    let body: serde_json::Value = serde_json::from_slice(&body_bytes)?;
    let pid = body.get("process_id").and_then(|v| v.as_str()).unwrap_or("unknown");
    let role = body.get("role").and_then(|v| v.as_str()).unwrap_or("leader");

    println!("HEARTBEAT: user={} role={} pid={}", user_id, role, pid);

    let db_url = variables::get("db_url").or_else(|_| variables::get("neon_db_url"))?;
    let connection = Connection::open(&db_url)?;
    
    // Atomic leadership/heartbeat claim with user scoping
    let update_query = if role == "leader" {
        "INSERT INTO scheduler_election (user_id, role, process_id, heartbeat) 
         VALUES ($1, 'leader', $2, CURRENT_TIMESTAMP) 
         ON CONFLICT (user_id, role) DO UPDATE SET 
             process_id = EXCLUDED.process_id, 
             heartbeat = CURRENT_TIMESTAMP 
         WHERE scheduler_election.process_id = $2 
            OR scheduler_election.heartbeat < CURRENT_TIMESTAMP - INTERVAL '90 seconds'
            OR scheduler_election.process_id IS NULL"
    } else {
        "INSERT INTO scheduler_election (user_id, role, process_id, heartbeat) 
         VALUES ($1, $3, $2, CURRENT_TIMESTAMP) 
         ON CONFLICT (user_id, role) DO UPDATE SET 
             process_id = EXCLUDED.process_id, 
             heartbeat = CURRENT_TIMESTAMP"
    };
    
    let params = if role == "leader" {
        vec![ParameterValue::Str(user_id.clone()), ParameterValue::Str(pid.to_string())]
    } else {
        vec![ParameterValue::Str(user_id.clone()), ParameterValue::Str(pid.to_string()), ParameterValue::Str(role.to_string())]
    };

    let result = connection.execute(update_query, &params)?;
    let claimed = result > 0;

    // Check if MCP (home server) is active for this user
    let mcp_active_query = "SELECT EXISTS(SELECT 1 FROM scheduler_election WHERE user_id = $1 AND role = 'leader' AND heartbeat > CURRENT_TIMESTAMP - INTERVAL '90 seconds')";
    let mcp_rows = connection.query(mcp_active_query, &[ParameterValue::Str(user_id)])?;
    let mcp_server_active = match mcp_rows.rows.first() {
        Some(row) => match &row[0] {
            DbValue::Boolean(b) => *b,
            _ => false,
        },
        None => false,
    };

    #[derive(Serialize)]
    struct HeartbeatResponse {
        status: String,
        is_leader: bool,
        mcp_server_active: bool,
    }
    let resp = HeartbeatResponse { 
        status: "ok".to_string(), 
        is_leader: claimed,
        mcp_server_active
    };

    Ok(Response::builder()
        .status(200)
        .header("content-type", "application/json")
        .body(serde_json::to_string(&resp).unwrap())
        .build())
}

#[derive(Deserialize)]
struct MultiplierRequest {
    name: String,
    multiplier: f64,
}

async fn handle_multiplier_post(req: Request) -> anyhow::Result<Response> {
    let auth_header = req.header("authorization");
    let user_id = match extract_user_id(auth_header).await {
        Some(id) => id,
        None => return Ok(Response::builder().status(401).body("Unauthorized").build()),
    };

    let body_bytes = req.into_body();
    let body_str = std::str::from_utf8(&body_bytes).map_err(|_| anyhow::anyhow!("Invalid UTF-8"))?;
    let req_data: MultiplierRequest = serde_json::from_str(body_str)?;

    let db_url = variables::get("db_url").or_else(|_| variables::get("neon_db_url"))?;
    let connection = Connection::open(&db_url)?;

    println!("Updating multiplier for user {}: {} -> {}", user_id, req_data.name, req_data.multiplier);

    // Explicit cast string to NUMERIC
    let query = "UPDATE language_stats SET pump_multiplier = $1::FLOAT8::NUMERIC WHERE user_id = $2 AND language_name = $3";
    match connection.execute(query, &[
        ParameterValue::Floating64(req_data.multiplier), 
        ParameterValue::Str(user_id), 
        ParameterValue::Str(req_data.name.to_uppercase())
    ]) {
        Ok(_) => Ok(Response::builder().status(200).body("Multiplier updated").build()),
        Err(e) => {
            let error_msg = format!("DB Error: {}", e);
            eprintln!("{}", error_msg);
            let resp = StatusResponse { status: "error".to_string(), message: error_msg };
            Ok(Response::builder().status(500).header("content-type", "application/json").body(serde_json::to_string(&resp).unwrap()).build())
        }
    }
}

async fn handle_languages_get(req: Request) -> anyhow::Result<Response> {
    let auth_header = req.header("authorization");
    let user_id = match extract_user_id(auth_header).await {
        Some(id) => id,
        None => return Ok(Response::builder().status(401).body("Unauthorized").build()),
    };

    let db_url = variables::get("db_url").or_else(|_| variables::get("neon_db_url"))?;
    let connection = Connection::open(&db_url)?;
    
    let query = "SELECT language_name, current_reviews, tomorrow_reviews, next_7_days_reviews, daily_rate::FLOAT8, safebuf, derail_risk, pump_multiplier::FLOAT8, beeminder_slug, daily_completions FROM language_stats WHERE user_id = $1";
    let row_set = connection.query(query, &[ParameterValue::Str(user_id)])?;

    #[derive(Serialize)]
    struct LanguageStat {
        name: String,
        current: i32,
        tomorrow: i32,
        next_7_days: i32,
        daily_rate: f64,
        safebuf: i32,
        derail_risk: String,
        pump_multiplier: f64,
        has_goal: bool,
        daily_completions: i32,
    }

    #[derive(Serialize)]
    struct LanguagesResponse {
        languages: Vec<LanguageStat>,
    }

    let mut languages: Vec<LanguageStat> = row_set.rows.iter().map(|row| {
        let name = match &row[0] { DbValue::Str(s) => s.clone(), _ => "".to_string() };
        let slug = match &row[8] { DbValue::Str(s) => Some(s.clone()), _ => None };
        
        // Canonical/Autodata goals (GREEK) should be treated as having a goal even without a sync slug.
        let is_canonical = name.to_uppercase() == "GREEK";
        let has_goal = is_canonical || slug.as_ref().map_or(false, |s| !s.is_empty());
        
        LanguageStat {
            name,
            current: match &row[1] { DbValue::Int32(i) => *i, _ => 0 },
            tomorrow: match &row[2] { DbValue::Int32(i) => *i, _ => 0 },
            next_7_days: match &row[3] { DbValue::Int32(i) => *i, _ => 0 },
            daily_rate: match &row[4] { DbValue::Floating64(f) => *f, _ => 0.0 },
            safebuf: match &row[5] { DbValue::Int32(i) => *i, _ => 0 },
            derail_risk: match &row[6] { DbValue::Str(s) => s.clone(), _ => "SAFE".to_string() },
            pump_multiplier: match &row[7] { DbValue::Floating64(f) => *f, _ => 1.0 },
            has_goal,
            daily_completions: match &row[9] { DbValue::Int32(i) => *i, _ => 0 },
        }
    }).collect();

    // Filter out languages with 0 reviews AND 0 completions (don't show empty/unused languages)
    languages.retain(|l| l.current > 0 || l.daily_completions > 0);

    // Sort: Languages with goals first, then by shortest runway (safebuf)
    languages.sort_by(|a, b| {
        if a.has_goal != b.has_goal {
            b.has_goal.cmp(&a.has_goal) // true comes before false
        } else if a.has_goal {
            a.safebuf.cmp(&b.safebuf) // shortest runway first
        } else {
            b.current.cmp(&a.current) // for non-goal items, highest debt first
        }
    });

    let resp = LanguagesResponse { languages };
    Ok(Response::builder().status(200).header("content-type", "application/json").body(serde_json::to_string(&resp).unwrap()).build())
}

async fn handle_budget_get(req: Request) -> anyhow::Result<Response> {
    let auth_header = req.header("authorization");
    let user_id = match extract_user_id(auth_header).await {
        Some(id) => id,
        None => return Ok(Response::builder().status(401).body("Unauthorized").build()),
    };

    let db_url = variables::get("db_url").or_else(|_| variables::get("neon_db_url"))?;
    let connection = Connection::open(&db_url)?;
    
    let query = "SELECT remaining_budget FROM budget_tracking WHERE user_id = $1 LIMIT 1";
    let row_set = connection.query(query, &[ParameterValue::Str(user_id)])?;
    
    let remaining_budget = if row_set.rows.is_empty() {
        0.0
    } else {
        match &row_set.rows[0][0] {
            DbValue::Floating64(f) => *f,
            DbValue::Floating32(f) => *f as f64,
            _ => 0.0
        }
    };

    #[derive(Serialize)]
    struct BudgetResponse {
        remaining_budget: f64,
    }
    
    let resp = BudgetResponse { remaining_budget };
    Ok(Response::builder().status(200).header("content-type", "application/json").body(serde_json::to_string(&resp).unwrap()).build())
}

async fn handle_walks_post(req: Request) -> anyhow::Result<Response> {
    let auth_header = req.header("authorization");
    let user_id = match extract_user_id(auth_header).await {
        Some(id) => id,
        None => return Ok(Response::builder().status(401).body("Unauthorized").build()),
    };

    let body_bytes = req.body();
    let walk: WalkDataSummary = serde_json::from_slice(body_bytes)?;

    let db_url = variables::get("db_url").or_else(|_| variables::get("neon_db_url"))?;
    let connection = Connection::open(&db_url)?;

    let _ = connection.execute(
        "INSERT INTO users (pocket_id_sub, beeminder_token_encrypted, beeminder_goal) VALUES ($1, '', 'bike') ON CONFLICT DO NOTHING",
        &[ParameterValue::Str(user_id.clone())]
    );

    let prev_distance_query = "SELECT distance_meters FROM walk_inferences WHERE user_id = $1 AND start_time = $2";
    let prev_distance_rs = connection.query(prev_distance_query, &[
        ParameterValue::Str(user_id.clone()),
        ParameterValue::Str(walk.start_time.clone())
    ])?;
    
    let previous_distance_str = if !prev_distance_rs.rows.is_empty() {
        match &prev_distance_rs.rows[0][0] {
            DbValue::Str(s) => s.clone(),
            _ => "0".to_string()
        }
    } else {
        "0".to_string()
    };
    
    let previous_distance: f64 = previous_distance_str.parse().unwrap_or(0.0);
    let delta_meters = walk.distance_meters - previous_distance;

    let query = r#"
        INSERT INTO walk_inferences (user_id, start_time, end_time, step_count, distance_meters, distance_source, confidence_score, gps_route_points, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'logging')
        ON CONFLICT (user_id, start_time) DO UPDATE SET end_time = EXCLUDED.end_time, step_count = EXCLUDED.step_count, distance_meters = EXCLUDED.distance_meters, status = 'logging'
    "#;

    connection.execute(query, &[
        ParameterValue::Str(user_id.clone()),
        ParameterValue::Str(walk.start_time.clone()),
        ParameterValue::Str(walk.end_time.clone()),
        ParameterValue::Str(walk.step_count.to_string()),
        ParameterValue::Str(walk.distance_meters.to_string()),
        ParameterValue::Str(walk.distance_source.clone()),
        ParameterValue::Str(walk.confidence_score.to_string()),
        ParameterValue::Str(walk.gps_route_points.to_string()),
    ])?;

    // Restore Beeminder Sync with delta
    let token_rs = connection.query(
        "SELECT beeminder_goal FROM users WHERE pocket_id_sub = $1",
        &[ParameterValue::Str(user_id.clone())]
    )?;

    if !token_rs.rows.is_empty() && delta_meters > 10.0 {
        let goal = match &token_rs.rows[0][0] { DbValue::Str(s) if !s.is_empty() => s.clone(), _ => "bike".to_string() };
        let total_miles = walk.distance_meters / 1609.34;
        let rounded_miles = (total_miles * 1000.0).round() / 1000.0;
        let _ = push_to_beeminder(&user_id, &goal, rounded_miles, "Synced via Spin (Cumulative)", &connection).await;
    }

    let resp = StatusResponse { status: "success".to_string(), message: "Walk ingested".to_string() };
    Ok(Response::builder().status(201).header("content-type", "application/json").body(serde_json::to_string(&resp).unwrap()).build())
}

// --- Twilio WhatsApp helpers (Phase 2 of kingdonb/mecris#166/#167) ---

fn build_twilio_url(account_sid: &str) -> String {
    format!("https://api.twilio.com/2010-04-01/Accounts/{}/Messages.json", account_sid)
}

fn build_twilio_body(from: &str, to: &str, message: &str) -> String {
    let whatsapp_from = if from.starts_with("whatsapp:") { from.to_string() } else { format!("whatsapp:{}", from) };
    let whatsapp_to = if to.starts_with("whatsapp:") { to.to_string() } else { format!("whatsapp:{}", to) };
    
    format!(
        "From={}&To={}&Body={}",
        urlencoding::encode(&whatsapp_from),
        urlencoding::encode(&whatsapp_to),
        urlencoding::encode(message)
    )
}

fn encode_basic_auth(username: &str, password: &str) -> String {
    use base64::Engine;
    let credentials = format!("{}:{}", username, password);
    base64::engine::general_purpose::STANDARD.encode(credentials.as_bytes())
}

/// Assemble Twilio SMS request components as plain strings. Pure function — fully unit-testable.
/// Returns `(url, form_body, authorization_header_value)`.
fn build_sms_request_parts(
    account_sid: &str,
    auth_token: &str,
    from: &str,
    to: &str,
    message: &str,
) -> (String, String, String) {
    let url = build_twilio_url(account_sid);
    let body = build_twilio_body(from, to, message);
    let auth = format!("Basic {}", encode_basic_auth(account_sid, auth_token));
    (url, body, auth)
}

/// Send a single Twilio SMS. Requires Spin host for the HTTP dispatch.
async fn send_walk_reminder(
    phone: &str,
    message: &str,
    account_sid: &str,
    auth_token: &str,
    from_number: &str,
    content_sid: Option<&str>,
    content_variables: Option<&str>,
) -> anyhow::Result<()> {
    let (url, mut body, auth) = build_sms_request_parts(account_sid, auth_token, from_number, phone, message);
    
    // If a template SID is provided, append it to the body along with variables.
    if let Some(sid) = content_sid {
        body = format!("{}&ContentSid={}", body, urlencoding::encode(sid));
        if let Some(vars) = content_variables {
            body = format!("{}&ContentVariables={}", body, urlencoding::encode(vars));
        }
    }

    let req = Request::post(url, body)
        .header("content-type", "application/x-www-form-urlencoded")
        .header("Authorization", auth)
        .build();
    let res: Response = spin_sdk::http::send(req).await?;
    if !(200..300).contains(res.status()) {
        let err_body = std::str::from_utf8(res.body()).unwrap_or("");
        println!("Twilio SMS FAILED: {} - Body: {}", res.status(), err_body);
        return Err(anyhow::anyhow!("Twilio SMS failed with status {}", res.status()));
    }
    println!("Twilio SMS SENT to {}", phone);
    Ok(())
}

async fn handle_trigger_reminders_post(_req: Request) -> anyhow::Result<Response> {
    // Phase 2 implementation — yebyen/mecris#148
    let account_sid = match variables::get("twilio_account_sid") {
        Ok(s) if !s.is_empty() => s,
        _ => {
            let resp = StatusResponse {
                status: "error".to_string(),
                message: "twilio_account_sid not configured".to_string(),
            };
            return Ok(Response::builder()
                .status(500)
                .header("content-type", "application/json")
                .body(serde_json::to_string(&resp).unwrap())
                .build());
        }
    };

    let auth_token_enc = match variables::get("twilio_auth_token_encrypted") {
        Ok(s) if !s.is_empty() => s,
        _ => {
            let resp = StatusResponse {
                status: "error".to_string(),
                message: "twilio_auth_token_encrypted not configured".to_string(),
            };
            return Ok(Response::builder()
                .status(500)
                .header("content-type", "application/json")
                .body(serde_json::to_string(&resp).unwrap())
                .build());
        }
    };

    let from_number = match variables::get("twilio_from_number") {
        Ok(s) if !s.is_empty() => s,
        _ => {
            let resp = StatusResponse {
                status: "error".to_string(),
                message: "twilio_from_number not configured".to_string(),
            };
            return Ok(Response::builder()
                .status(500)
                .header("content-type", "application/json")
                .body(serde_json::to_string(&resp).unwrap())
                .build());
        }
    };

    let auth_token = match decrypt_token(&auth_token_enc).await {
        Ok(t) => t,
        Err(e) => {
            let resp = StatusResponse {
                status: "error".to_string(),
                message: format!("Failed to decrypt Twilio auth token: {}", e),
            };
            return Ok(Response::builder()
                .status(500)
                .header("content-type", "application/json")
                .body(serde_json::to_string(&resp).unwrap())
                .build());
        }
    };

    let db_url = variables::get("db_url").or_else(|_| variables::get("neon_db_url"))?;
    let connection = Connection::open(&db_url)?;

    // Include per-user location columns; COALESCE to empty string so absent values parse as None.
    let query = "SELECT pocket_id_sub, phone_number_encrypted, COALESCE(timezone, 'UTC'), \
                 COALESCE(location_lat::TEXT, ''), COALESCE(location_lon::TEXT, '') \
                 FROM users WHERE phone_number_encrypted IS NOT NULL AND phone_number_encrypted != '' \
                 AND autonomous_sync_enabled = true";
    let row_set = connection.query(query, &[])?;

    let now_utc = chrono::Utc::now();
    let today_utc = now_utc.format("%Y-%m-%d").to_string();
    let now_epoch_secs = now_utc.timestamp() as u64;

    // Pre-fetch global Spin vars for weather — used as fallback when user has no per-user location.
    let openweather_api_key = variables::get("openweather_api_key").ok().filter(|s| !s.is_empty());
    let global_lat_str = variables::get("openweather_lat").ok().filter(|s| !s.is_empty());
    let global_lon_str = variables::get("openweather_lon").ok().filter(|s| !s.is_empty());

    let mut sent = 0u32;
    let mut errors = 0u32;

    for row in &row_set.rows {
        let user_id = match &row[0] { DbValue::Str(s) => s.clone(), _ => continue };

        // Register heartbeat for this cloud instance
        let _ = register_cloud_heartbeat(&connection, &user_id).await;
        let phone_enc = match &row[1] { DbValue::Str(s) if !s.is_empty() => s.clone(), _ => continue };
        let timezone = match &row[2] { DbValue::Str(s) => s.clone(), _ => "UTC".to_string() };
        let user_lat_str = match &row[3] { DbValue::Str(s) if !s.is_empty() => Some(s.as_str()), _ => None };
        let user_lon_str = match &row[4] { DbValue::Str(s) if !s.is_empty() => Some(s.as_str()), _ => None };

        // Phase 3: timezone-aware local hour
        let local_hour = local_hour_from_timezone(&timezone, &now_utc);

        // Phase 3: step count from walk_inferences for today
        let step_strings: Vec<String> = match connection.query(
            "SELECT step_count FROM walk_inferences WHERE user_id = $1 AND start_time >= $2 ORDER BY start_time ASC",
            &[ParameterValue::Str(user_id.clone()), ParameterValue::Str(today_utc.clone())],
        ) {
            Ok(rs) => rs.rows.iter()
                .filter_map(|r| match &r[0] { DbValue::Str(s) => Some(s.clone()), _ => None })
                .collect(),
            Err(_) => vec![],
        };
        let step_count = aggregate_step_count(&step_strings);

        // Phase 3: rate limit via message_log
        let last_sent_at: Option<String> = match connection.query(
            "SELECT sent_at::TEXT FROM message_log WHERE user_id = $1 AND type = 'walk_reminder' ORDER BY sent_at DESC LIMIT 1",
            &[ParameterValue::Str(user_id.clone())],
        ) {
            Ok(rs) => rs.rows.first()
                .and_then(|r| match &r[0] { DbValue::Str(s) if !s.is_empty() => Some(s.clone()), _ => None }),
            Err(_) => None,
        };
        let minutes_since_last = minutes_since_last_reminder(last_sent_at.as_deref(), now_epoch_secs);

        if !should_dispatch_reminder(local_hour, step_count, minutes_since_last) {
            println!("Skipping reminder for user {} (hour={}, steps={}, mins_since_last={:?})", user_id, local_hour, step_count, minutes_since_last);
            continue;
        }

        // Ghost Nag prevention (kingdonb/mecris#191): if Android client has heartbeated within
        // the past 4 hours, it is handling local nags — Cloud stands down to avoid double-fire.
        let android_heartbeat_minutes: Option<u64> = match connection.query(
            "SELECT EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - heartbeat)) / 60 AS minutes_since \
             FROM scheduler_election WHERE user_id = $1 AND role = 'android_client' \
             ORDER BY heartbeat DESC LIMIT 1",
            &[ParameterValue::Str(user_id.clone())],
        ) {
            Ok(rs) => rs.rows.first().and_then(|r| match &r[0] {
                DbValue::Floating64(f) => Some(*f as u64),
                DbValue::Str(s) => s.parse::<f64>().ok().map(|f| f as u64),
                _ => None,
            }),
            Err(_) => None,
        };
        if android_client_is_active(android_heartbeat_minutes) {
            println!("Ghost Nag guard: skipping cloud reminder for user {} — Android heartbeat {}min ago", user_id, android_heartbeat_minutes.unwrap_or(0));
            continue;
        }

        // Phase 3: Per-user weather check — suppress reminder if weather is bad at user's location.
        // Resolves per-user location first; falls back to global Spin vars if not set.
        // Graceful degradation: if no location or API key, proceed without weather check.
        if let Some(api_key) = &openweather_api_key {
            if let Some((lat, lon)) = resolve_lat_lon(user_lat_str, user_lon_str, global_lat_str.as_deref(), global_lon_str.as_deref()) {
                match fetch_weather_full(lat, lon, api_key).await {
                    Ok(w) => {
                        let weather_main = w.weather.get(0).map(|c| c.main.as_str()).unwrap_or("");
                        if !is_weather_ok_for_walk(weather_main) {
                            println!("Skipping reminder for user {} — weather unsuitable ({})", user_id, weather_main);
                            continue;
                        }
                        println!("Weather ok for user {} ({}), proceeding", user_id, weather_main);
                    }
                    Err(e) => {
                        eprintln!("OpenWeather check failed for user {} ({}), proceeding", user_id, e);
                    }
                }
            }
        }

        match decrypt_token(&phone_enc).await {
            Ok(phone) => {
                let message = "Time for a walk with Boris and Fiona! 🐕 Check your daily goal.";
                let template_sid = variables::get("twilio_whatsapp_template_sid").ok();
                
                // Map to mecris_status_v2: {{1}} is currently {{2}}. {{3}} is {{4}}. Review {{5}}.
                let content_vars = template_sid.as_ref().map(|_| {
                    serde_json::json!({
                        "1": "Physical",
                        "2": "PENDING",
                        "3": "Steps",
                        "4": "low",
                        "5": "Daily"
                    }).to_string()
                });

                match send_walk_reminder(
                    &phone, 
                    message, 
                    &account_sid, 
                    &auth_token, 
                    &from_number,
                    template_sid.as_deref(),
                    content_vars.as_deref()
                ).await {
                    Ok(_) => {
                        println!("Reminder sent to user {}", user_id);
                        let _ = connection.execute(
                            "INSERT INTO message_log (user_id, type, channel) VALUES ($1, 'walk_reminder', 'sms')",
                            &[ParameterValue::Str(user_id.clone())],
                        );
                        sent += 1;
                    }
                    Err(e) => {
                        eprintln!("Failed to send reminder to user {}: {}", user_id, e);
                        errors += 1;
                    }
                }
            }
            Err(e) => {
                eprintln!("Failed to decrypt phone for user {}: {}", user_id, e);
                errors += 1;
            }
        }
    }

    let resp = StatusResponse {
        status: "ok".to_string(),
        message: format!("Sent {} reminders, {} errors", sent, errors),
    };
    Ok(Response::builder()
        .status(200)
        .header("content-type", "application/json")
        .body(serde_json::to_string(&resp).unwrap())
        .build())
}

async fn handle_failover_sync_post(_req: Request) -> anyhow::Result<Response> {
    let db_url = variables::get("db_url")
        .or_else(|_| variables::get("neon_db_url"))
        .map_err(|e| anyhow::anyhow!("db_url/neon_db_url fetch failed: {:?}", e))?;
    let connection = Connection::open(&db_url)?;

    let query = "SELECT pocket_id_sub, EXTRACT(EPOCH FROM CURRENT_TIMESTAMP - COALESCE(last_autonomous_sync, '1970-01-01'::TIMESTAMPTZ))/60 AS mins_since \
                 FROM users WHERE autonomous_sync_enabled = true";
    let row_set = connection.query(query, &[])?;
    
    let mut success_count = 0;
    for row in &row_set.rows {
        let user_id = match &row[0] { DbValue::Str(s) => s.clone(), _ => continue };

        // Register heartbeat for this cloud instance
        let _ = register_cloud_heartbeat(&connection, &user_id).await;
        let mins_since = match &row[1] { 
            DbValue::Floating64(f) => Some(*f as u64),
            _ => None 
        };

        if !is_autonomous_sync_allowed(true, mins_since) {
            continue;
        }

        match run_clozemaster_scraper(&db_url, &user_id).await {
            Ok(_) => {
                let _ = connection.execute(
                    "UPDATE users SET last_autonomous_sync = CURRENT_TIMESTAMP WHERE pocket_id_sub = $1",
                    &[ParameterValue::Str(user_id)]
                );
                success_count += 1;
            }
            Err(e) => {
                eprintln!("Autonomous sync failed for user {}: {:?}", user_id, e);
            }
        }
    }
    
    let resp = StatusResponse { status: "success".to_string(), message: format!("Cloud sync processed for {} users", success_count) };
    Ok(Response::builder().status(200).header("content-type", "application/json").body(serde_json::to_string(&resp).unwrap()).build())
}

#[derive(Deserialize)]
struct VerificationRequest {
    phone_number: String,
}

#[derive(Deserialize)]
struct VerificationConfirmRequest {
    code: String,
}

async fn handle_request_phone_verification_post(req: Request) -> anyhow::Result<Response> {
    let auth_header = req.header("authorization");
    let user_id = match extract_user_id(auth_header).await {
        Some(id) => id,
        None => {
            println!("Phone Verification: Unauthorized request (no valid token)");
            return Ok(Response::builder().status(401).body("Unauthorized").build());
        }
    };

    let body = req.body();
    let verify_req: VerificationRequest = serde_json::from_slice(body)?;
    println!("Phone Verification: Request for user {} to {}", user_id, verify_req.phone_number);
    
    let db_url = variables::get("db_url").or_else(|_| variables::get("neon_db_url"))?;
    let connection = Connection::open(&db_url)?;

    // 1. Generate 6-digit code
    use getrandom::getrandom;
    let mut rand_bytes = [0u8; 4];
    getrandom(&mut rand_bytes)?;
    let code = (u32::from_be_bytes(rand_bytes) % 900000 + 100000).to_string();
    println!("Phone Verification: Generated code {} for user {}", code, user_id);

    // 2. Hash code for storage (Simple SHA1 for now, already imported)
    use sha1::{Sha1, Digest};
    let mut hasher = Sha1::new();
    hasher.update(code.as_bytes());
    let code_hash = hex::encode(hasher.finalize());

    // 3. Upsert into phone_verifications (15 min expiry)
    let query = "INSERT INTO phone_verifications (user_id, code_hash, expires_at) VALUES ($1, $2, NOW() + INTERVAL '15 minutes') \
                 ON CONFLICT (user_id) DO UPDATE SET code_hash = $2, expires_at = NOW() + INTERVAL '15 minutes', attempts = 0";
    connection.execute(query, &[
        ParameterValue::Str(user_id.clone()),
        ParameterValue::Str(code_hash),
    ])?;

    // 4. Send SMS via Twilio
    let account_sid = variables::get("twilio_account_sid")?;
    let auth_token_enc = variables::get("twilio_auth_token_encrypted")?;
    let from_number = variables::get("twilio_from_number")?;
    let auth_token = decrypt_token(&auth_token_enc).await?;

    let message = format!("Mecris: Your verification code is {}. Enter this in settings to confirm your phone number.", code);
    let template_sid = variables::get("twilio_whatsapp_template_sid").ok();

    // Map to mecris_status_v2: {{1}} is currently {{2}}. {{3}} is {{4}}. Review {{5}}.
    let content_vars = template_sid.as_ref().map(|_| {
        serde_json::json!({
            "1": "Identity",
            "2": "PENDING",
            "3": "Code",
            "4": code,
            "5": "Account"
        }).to_string()
    });

    match send_walk_reminder(
        &verify_req.phone_number, 
        &message, 
        &account_sid, 
        &auth_token, 
        &from_number,
        template_sid.as_deref(),
        content_vars.as_deref()
    ).await {
        Ok(_) => {
            let resp = StatusResponse { status: "success".to_string(), message: "Verification code sent".to_string() };
            Ok(Response::builder().status(200).header("content-type", "application/json").body(serde_json::to_string(&resp).unwrap()).build())
        }
        Err(e) => {
            let resp = StatusResponse { status: "error".to_string(), message: format!("Failed to send SMS: {}", e) };
            Ok(Response::builder().status(500).header("content-type", "application/json").body(serde_json::to_string(&resp).unwrap()).build())
        }
    }
}

async fn handle_confirm_phone_verification_post(req: Request) -> anyhow::Result<Response> {
    let auth_header = req.header("authorization");
    let user_id = match extract_user_id(auth_header).await {
        Some(id) => id,
        None => return Ok(Response::builder().status(401).body("Unauthorized").build()),
    };

    let body = req.body();
    let body_str = std::str::from_utf8(body).unwrap_or("");
    println!("Phone Verification: Confirm for user {} - Body: {}", user_id, body_str);
    
    let confirm_req: VerificationConfirmRequest = match serde_json::from_slice(body) {
        Ok(r) => r,
        Err(e) => {
            println!("Phone Verification: JSON Parse FAILED: {}", e);
            let resp = StatusResponse { status: "error".to_string(), message: format!("Invalid JSON: {}", e) };
            return Ok(Response::builder().status(400).header("content-type", "application/json").body(serde_json::to_string(&resp).unwrap()).build());
        }
    };

    let db_url = variables::get("db_url").or_else(|_| variables::get("neon_db_url"))?;
    let connection = Connection::open(&db_url)?;

    // 1. Fetch verification record
    let query = "SELECT code_hash, CAST(EXTRACT(EPOCH FROM expires_at) AS BIGINT) as expires_at_epoch, attempts FROM phone_verifications WHERE user_id = $1";
    let rs = connection.query(query, &[ParameterValue::Str(user_id.clone())])?;
    if rs.rows.is_empty() {
        let resp = StatusResponse { status: "error".to_string(), message: "No verification request found".to_string() };
        return Ok(Response::builder().status(400).header("content-type", "application/json").body(serde_json::to_string(&resp).unwrap()).build());
    }

    let stored_hash = match &rs.rows[0][0] { DbValue::Str(s) => s.clone(), _ => "".to_string() };
    let expires_at_epoch = match &rs.rows[0][1] { 
        DbValue::Int64(i) => *i,
        DbValue::Floating64(f) => *f as i64,
        _ => {
            println!("Phone Verification: UNEXPECTED DB TYPE for epoch: {:?}", rs.rows[0][1]);
            0
        }
    };
    let attempts = match &rs.rows[0][2] { DbValue::Int32(i) => *i, _ => 0 };

    if attempts >= 5 {
        return Ok(Response::builder().status(429).body("Too many attempts").build());
    }

    // 2. Check expiry
    let now_epoch = chrono::Utc::now().timestamp();
    println!("Phone Verification: Expiry Check - Now: {}, Expires: {}, Delta: {}", now_epoch, expires_at_epoch, expires_at_epoch - now_epoch);
    
    if now_epoch > expires_at_epoch {
        println!("Phone Verification: CODE EXPIRED for user {}", user_id);
        return Ok(Response::builder().status(410).body("Code expired").build());
    }

    // 3. Hash provided code and compare
    use sha1::{Sha1, Digest};
    let mut hasher = Sha1::new();
    hasher.update(confirm_req.code.as_bytes());
    let provided_hash = hex::encode(hasher.finalize());

    if provided_hash == stored_hash {
        println!("Phone Verification: SUCCESS for user {}", user_id);
        connection.execute("UPDATE users SET phone_verified = true WHERE pocket_id_sub = $1", &[ParameterValue::Str(user_id.clone())])?;
        connection.execute("DELETE FROM phone_verifications WHERE user_id = $1", &[ParameterValue::Str(user_id)])?;

        let resp = StatusResponse { status: "success".to_string(), message: "Phone number verified".to_string() };
        Ok(Response::builder().status(200).header("content-type", "application/json").body(serde_json::to_string(&resp).unwrap()).build())
    } else {
        connection.execute("UPDATE phone_verifications SET attempts = attempts + 1 WHERE user_id = $1", &[ParameterValue::Str(user_id)])?;
        let resp = StatusResponse { status: "error".to_string(), message: "Invalid code".to_string() };
        Ok(Response::builder().status(401).header("content-type", "application/json").body(serde_json::to_string(&resp).unwrap()).build())
    }
}

// --- Phase 3: Reminder heuristics (pure, unit-testable) ---

/// OpenWeather Current Weather API response shape.
#[derive(Deserialize, Debug)]
struct OpenWeatherResponse {
    weather: Vec<OpenWeatherCondition>,
    main: OpenWeatherMain,
    sys: OpenWeatherSys,
    dt: u64, // Time of data calculation, unix, UTC
}

#[derive(Deserialize, Debug)]
struct OpenWeatherCondition {
    main: String,
    description: String,
}

#[derive(Deserialize, Debug)]
struct OpenWeatherMain {
    temp: f64,
}

#[derive(Deserialize, Debug)]
struct OpenWeatherSys {
    sunrise: u64,
    sunset: u64,
}

#[derive(Serialize, Debug)]
struct WeatherHeuristicResponse {
    is_walk_appropriate: bool,
    conditions: String,
    description: String,
    temperature: f64,
    sunrise: u64,
    sunset: u64,
    is_dark: bool,
    now_epoch: u64,
    data_ts: u64,
}

/// Returns true if the OpenWeather "main" condition category is suitable for an outdoor walk.
/// Conditions marked good: "Clear", "Clouds".
/// All others (Rain, Drizzle, Thunderstorm, Snow, Atmosphere, etc.) return false.
/// Unknown / empty strings default to false (conservative).
fn is_weather_ok_for_walk(weather_main: &str) -> bool {
    matches!(weather_main.trim(), "Clear" | "Clouds")
}

/// Calls the OpenWeather Current Weather API and returns the full response.
async fn fetch_weather_full(lat: f64, lon: f64, api_key: &str) -> anyhow::Result<OpenWeatherResponse> {
    let url = format!(
        "https://api.openweathermap.org/data/2.5/weather?lat={}&lon={}&appid={}&units=metric",
        lat, lon, api_key
    );
    let req = Request::get(url).build();
    let resp: Response = spin_sdk::http::send(req).await?;
    let body = resp.body();
    let parsed: OpenWeatherResponse = serde_json::from_slice(body)
        .map_err(|e| anyhow::anyhow!("Failed to parse OpenWeather response: {}", e))?;
    Ok(parsed)
}

async fn handle_weather_heuristic_get(req: Request) -> anyhow::Result<Response> {
    let query_str = req.query().trim_start_matches('?');
    println!("Weather Heuristic RAW QUERY: {}", query_str);
    
    let params: HashMap<String, String> = query_str.split('&').filter_map(|s| {
        let mut parts = s.splitn(2, '=');
        Some((parts.next()?.to_string(), parts.next()?.to_string()))
    }).collect();

    let lat: f64 = params.get("lat").and_then(|s| s.parse().ok()).unwrap_or(0.0);
    let lon: f64 = params.get("lon").and_then(|s| s.parse().ok()).unwrap_or(0.0);
    println!("Weather Heuristic PARSED: lat={}, lon={}", lat, lon);

    let api_key = match variables::get("openweather_api_key") {
        Ok(k) if !k.is_empty() => k,
        _ => return Ok(Response::builder().status(500).body("openweather_api_key not configured").build()),
    };

    match fetch_weather_full(lat, lon, &api_key).await {
        Ok(w) => {
            let weather_main = w.weather.get(0).map(|c| c.main.as_str()).unwrap_or("");
            let weather_desc = w.weather.get(0).map(|c| c.description.as_str()).unwrap_or("");
            let is_walk_appropriate = is_weather_ok_for_walk(weather_main);
            
            let now_epoch = chrono::Utc::now().timestamp() as u64;
            // Use current server time (now_epoch) for the darkness calculation
            let is_dark = is_it_dark(now_epoch, w.sys.sunrise, w.sys.sunset);

            let resp = WeatherHeuristicResponse {
                is_walk_appropriate,
                conditions: weather_main.to_string(),
                description: weather_desc.to_string(),
                temperature: w.main.temp,
                sunrise: w.sys.sunrise,
                sunset: w.sys.sunset,
                is_dark,
                now_epoch,
                data_ts: w.dt,
            };

            Ok(Response::builder()
                .status(200)
                .header("content-type", "application/json")
                .body(serde_json::to_string(&resp).unwrap())
                .build())
        }
        Err(e) => {
            Ok(Response::builder()
                .status(500)
                .body(format!("Failed to fetch weather: {}", e))
                .build())
        }
    }
}

/// Returns true if the reference time is before sunrise or after sunset.
fn is_it_dark(ref_ts: u64, sunrise: u64, sunset: u64) -> bool {
    ref_ts < sunrise || ref_ts > sunset
}

/// Resolves the effective (lat, lon) for an OpenWeather call given optional per-user and
/// global-fallback coordinate strings. Returns None if no valid coordinates are available.
///
/// Priority: per-user coordinates → global Spin variable fallback → None.
/// If the preferred source fails to parse, falls back to the next source.
fn resolve_lat_lon(
    user_lat: Option<&str>,
    user_lon: Option<&str>,
    global_lat: Option<&str>,
    global_lon: Option<&str>,
) -> Option<(f64, f64)> {
    // Try per-user location first
    if let (Some(lat_s), Some(lon_s)) = (user_lat, user_lon) {
        if let (Ok(lat), Ok(lon)) = (lat_s.parse::<f64>(), lon_s.parse::<f64>()) {
            return Some((lat, lon));
        }
    }
    // Fall back to global Spin variables
    if let (Some(lat_s), Some(lon_s)) = (global_lat, global_lon) {
        if let (Ok(lat), Ok(lon)) = (lat_s.parse::<f64>(), lon_s.parse::<f64>()) {
            return Some((lat, lon));
        }
    }
    None
}

/// Returns true if the local hour (0-23) is within the active reminder window.
/// Active window: 8 AM (inclusive) to 8 PM (exclusive). Outside is the sleep window.
fn is_within_reminder_window(local_hour: u32) -> bool {
    local_hour >= 8 && local_hour < 20
}

/// Returns true if the user's step count is below the walk goal threshold.
/// Default threshold per Phase 3 spec: 2000 steps.
fn is_below_step_threshold(step_count: u32, threshold: u32) -> bool {
    step_count < threshold
}

/// Returns true if rate limiting allows another reminder to be sent.
/// Rule: no more than 1 message per 4 hours → minimum 240 minutes between messages.
/// If no previous message exists (None), it is always safe to send.
fn is_rate_limit_ok(minutes_since_last: Option<u64>) -> bool {
    match minutes_since_last {
        None => true,
        Some(m) => m >= 240,
    }
}

/// Returns true if autonomous sync is enabled and debounce time (5 mins) has passed.
fn is_autonomous_sync_allowed(enabled: bool, minutes_since_last: Option<u64>) -> bool {
    if !enabled { return false; }
    match minutes_since_last {
        None => true,
        Some(m) => m >= 5,
    }
}

/// Combined heuristic: returns true only when all three conditions are satisfied.
/// - Local hour is within the active reminder window (8 AM–8 PM)
/// - Step count is below the 2000-step threshold
/// - Rate limit allows sending (≥30 min since last, or no prior message)
fn should_dispatch_reminder(local_hour: u32, step_count: u32, minutes_since_last: Option<u64>) -> bool {
    is_within_reminder_window(local_hour)
        && is_below_step_threshold(step_count, 2000)
        && is_rate_limit_ok(minutes_since_last)
}

/// Returns true if the Android client has a fresh heartbeat within the past 4 hours.
/// `heartbeat_age_minutes` is the age of the most recent `android_client` entry in
/// `scheduler_election`, in minutes. If None (no record), returns false so Cloud can send.
fn android_client_is_active(heartbeat_age_minutes: Option<u64>) -> bool {
    match heartbeat_age_minutes {
        Some(m) => m < 240,
        None => false,
    }
}

// --- Phase 3: I/O helper pure functions ---

/// Aggregates total step count from a list of `step_count` strings (from walk_inferences).
/// Non-parseable strings are treated as zero. Returns 0 for an empty slice.
fn aggregate_step_count(step_strings: &[String]) -> u32 {
    step_strings.iter()
        .filter_map(|s| s.trim().parse::<u32>().ok())
        .last()
        .unwrap_or(0)
}

/// Returns the local hour (0–23) for the given UTC instant in the named IANA timezone.
/// Falls back to UTC if the name cannot be parsed by chrono-tz.
fn local_hour_from_timezone(timezone_name: &str, now_utc: &chrono::DateTime<chrono::Utc>) -> u32 {
    use chrono::Timelike;
    if let Ok(tz) = timezone_name.trim().parse::<chrono_tz::Tz>() {
        now_utc.with_timezone(&tz).hour()
    } else {
        now_utc.hour()
    }
}

/// Returns the number of minutes elapsed since the last reminder was sent.
/// `last_sent_at` is an RFC 3339 or Postgres TIMESTAMPTZ string; `now_epoch_secs` is
/// the current time as Unix seconds. Returns `None` if no prior reminder is recorded.
fn minutes_since_last_reminder(last_sent_at: Option<&str>, now_epoch_secs: u64) -> Option<u64> {
    let s = last_sent_at?;
    let dt = chrono::DateTime::parse_from_rfc3339(s)
        .or_else(|_| chrono::DateTime::parse_from_str(s, "%Y-%m-%d %H:%M:%S%.f%z"))
        .ok()?;
    let sent_epoch = dt.timestamp() as u64;
    Some(now_epoch_secs.saturating_sub(sent_epoch) / 60)
}

// --- Twilio inbound webhook helpers (kingdonb/mecris#140) ---

/// Parse a single field from a URL form-encoded body string.
/// Handles `+` as space and percent-decoding.
fn parse_form_field(body: &str, field: &str) -> Option<String> {
    body.split('&').find_map(|pair| {
        let mut iter = pair.splitn(2, '=');
        let key = iter.next()?;
        let val = iter.next().unwrap_or("");
        if key == field {
            let plus_decoded = val.replace('+', " ");
            Some(urlencoding::decode(&plus_decoded).unwrap_or_default().into_owned())
        } else {
            None
        }
    })
}

/// Parse all fields from a URL form-encoded body into a list of decoded (key, value) pairs.
fn parse_form_body(body: &str) -> Vec<(String, String)> {
    body.split('&')
        .filter_map(|pair| {
            let mut iter = pair.splitn(2, '=');
            let key = iter.next().map(|s| {
                let plus = s.replace('+', " ");
                urlencoding::decode(&plus).unwrap_or_default().into_owned()
            })?;
            let val = iter.next().map(|s| {
                let plus = s.replace('+', " ");
                urlencoding::decode(&plus).unwrap_or_default().into_owned()
            }).unwrap_or_default();
            Some((key, val))
        })
        .collect()
}

/// Returns true if the Twilio SMS `Body` field contains an affirmative reply.
/// Matches case-insensitively: YES, Y, DONE, OK, 1, ✅.
fn is_affirmative_response(body: &str) -> bool {
    let sms_body = parse_form_field(body, "Body").unwrap_or_default();
    matches!(sms_body.trim().to_uppercase().as_str(), "YES" | "Y" | "DONE" | "OK" | "1" | "✅")
}

/// Validates a Twilio webhook request using HMAC-SHA1.
/// `auth_token` is the plaintext Twilio auth token.
/// `url` is the full URL of the webhook endpoint.
/// `params` is the decoded POST parameter list (key, value pairs) from the request body.
/// `signature` is the X-Twilio-Signature header value.
/// Returns true only if the computed signature matches.
fn validate_twilio_signature(auth_token: &str, url: &str, params: &[(String, String)], signature: &str) -> bool {
    use hmac::{Hmac, Mac};
    use sha1::Sha1;
    type HmacSha1 = Hmac<Sha1>;

    let mut sorted = params.to_vec();
    sorted.sort_by(|a, b| a.0.cmp(&b.0));

    let mut input = url.to_string();
    for (k, v) in &sorted {
        input.push_str(k);
        input.push_str(v);
    }

    let Ok(mut mac) = <HmacSha1 as KeyInit>::new_from_slice(auth_token.as_bytes()) else {
        return false;
    };
    mac.update(input.as_bytes());
    let result = mac.finalize().into_bytes();
    let computed = base64::engine::general_purpose::STANDARD.encode(result);
    computed == signature
}

/// Stub handler for incoming Twilio SMS webhooks (kingdonb/mecris#140).
/// Validates the Twilio HMAC-SHA1 signature, parses the response, and returns TwiML.
/// TODO: persist affirmative responses to DB and push Beeminder datapoints.
async fn handle_twilio_webhook_post(req: Request) -> anyhow::Result<Response> {
    let auth_token_enc = match variables::get("twilio_auth_token_encrypted") {
        Ok(s) if !s.is_empty() => s,
        _ => return Ok(Response::builder().status(503).body("twilio_auth_token_encrypted not configured").build()),
    };
    let auth_token = match decrypt_token(&auth_token_enc).await {
        Ok(t) => t,
        Err(e) => {
            println!("Twilio webhook: failed to decrypt auth token: {}", e);
            return Ok(Response::builder().status(503).body("Failed to decrypt auth token").build());
        }
    };

    let body_bytes = req.body();
    let body_str = std::str::from_utf8(body_bytes).unwrap_or("");

    let host = req.header("host").and_then(|v| v.as_str()).unwrap_or("localhost");
    let webhook_url = format!("https://{}{}", host, req.path());
    let params = parse_form_body(body_str);
    let sig_header = req.header("x-twilio-signature").and_then(|v| v.as_str()).unwrap_or("");

    if !validate_twilio_signature(&auth_token, &webhook_url, &params, sig_header) {
        println!("Twilio webhook: invalid signature (url={}, sig={})", webhook_url, sig_header);
        return Ok(Response::builder().status(403).body("Forbidden: Invalid Twilio Signature").build());
    }

    let twiml = if is_affirmative_response(body_str) {
        println!("Twilio webhook: affirmative response received");
        // TODO(kingdonb/mecris#140): persist activity log entry, push Beeminder datapoint
        r#"<?xml version="1.0" encoding="UTF-8"?><Response><Message>Logged. Great job!</Message></Response>"#
    } else {
        println!("Twilio webhook: non-affirmative response received");
        r#"<?xml version="1.0" encoding="UTF-8"?><Response><Message>Got it. Reply YES to log your activity.</Message></Response>"#
    };

    if is_affirmative_response(body_str) {
        if let Some(from_num) = extract_from_number(body_str) {
            match variables::get("db_url").or_else(|_| variables::get("neon_db_url")) {
                Ok(db_url) if !db_url.is_empty() => {
                    match Connection::open(&db_url) {
                        Ok(connection) => {
                            let query = "SELECT pocket_id_sub, phone_number_encrypted, beeminder_goal \
                                         FROM users WHERE phone_number_encrypted IS NOT NULL AND phone_number_encrypted != ''";
                            if let Ok(row_set) = connection.query(query, &[]) {
                                for row in &row_set.rows {
                                    let user_id = match &row[0] { DbValue::Str(s) => s.clone(), _ => continue };
                                    let phone_enc = match &row[1] { DbValue::Str(s) if !s.is_empty() => s.clone(), _ => continue };
                                    let beeminder_goal = match &row[2] { DbValue::Str(s) if !s.is_empty() => s.clone(), _ => "bike".to_string() };
                                    if let Ok(phone) = decrypt_token(&phone_enc).await {
                                        if phones_match(&phone, &from_num) {
                                            let comment = "Walk logged via SMS reply";
                                            let _ = push_to_beeminder(&user_id, &beeminder_goal, 1.0, comment, &connection).await;
                                            let _ = connection.execute(
                                                "INSERT INTO message_log (user_id, type, channel) VALUES ($1, 'walk_ack', 'sms')",
                                                &[ParameterValue::Str(user_id.clone())],
                                            );
                                            println!("Twilio webhook: walk_ack logged for user {} via {}", user_id, from_num);
                                            break;
                                        }
                                    }
                                }
                            }
                        }
                        Err(e) => eprintln!("Twilio webhook: DB connect failed: {}", e),
                    }
                }
                _ => eprintln!("Twilio webhook: db_url not configured, skipping DB+Beeminder wiring"),
            }
        }
    }

    Ok(Response::builder()
        .status(200)
        .header("content-type", "text/xml")
        .body(twiml)
        .build())
}

/// Extracts the `From` phone number from a Twilio webhook form-encoded body.
/// Returns None if the field is absent or empty.
fn extract_from_number(body: &str) -> Option<String> {
    parse_form_field(body, "From").filter(|s| !s.is_empty())
}

/// Builds the form-encoded POST body for a Beeminder datapoints API call.
/// `auth_token` must be the plaintext token (decrypted by caller from DB).
fn build_beeminder_datapoint_body(auth_token: &str, value: f64, comment: &str) -> String {
    format!(
        "auth_token={}&value={}&comment={}",
        auth_token,
        value,
        urlencoding::encode(comment)
    )
}

/// Normalizes a phone number to E.164 digits-and-plus for comparison.
/// Strips spaces, dashes, parentheses, and dots. Keeps the leading `+`.
fn normalize_phone(phone: &str) -> String {
    phone.chars().filter(|c| c.is_ascii_digit() || *c == '+').collect()
}

/// Returns true if two phone numbers refer to the same subscriber after normalization.
fn phones_match(a: &str, b: &str) -> bool {
    !a.is_empty() && !b.is_empty() && normalize_phone(a) == normalize_phone(b)
}

/// Returns true if the request is authorized to call an `/internal/*` endpoint.
///
/// If `configured_key` is empty (the `internal_api_key` Spin variable is unset), all requests
/// are allowed — backwards compatible for deployments without a key configured.
/// If `configured_key` is non-empty, the caller must supply a matching `X-Internal-Api-Key`
/// header value; any mismatch or absent header is rejected.
fn internal_api_key_ok(configured_key: &str, req_header: Option<&str>) -> bool {
    if configured_key.is_empty() {
        return true;
    }
    req_header.map_or(false, |v| v == configured_key)
}

#[cfg(test)]
mod tests {
    use super::*;

    // --- is_autonomous_sync_allowed ---

    #[test]
    fn test_autonomous_sync_not_allowed_when_disabled() {
        assert!(!is_autonomous_sync_allowed(false, None));
    }

    #[test]
    fn test_autonomous_sync_allowed_when_enabled_and_no_prior_sync() {
        assert!(is_autonomous_sync_allowed(true, None));
    }

    #[test]
    fn test_autonomous_sync_not_allowed_when_debounced_under_5_mins() {
        assert!(!is_autonomous_sync_allowed(true, Some(4)));
    }

    #[test]
    fn test_autonomous_sync_allowed_when_debounced_5_mins_or_more() {
        assert!(is_autonomous_sync_allowed(true, Some(5)));
        assert!(is_autonomous_sync_allowed(true, Some(60)));
    }

    // --- should_delegate ---

    #[test]
    fn test_should_delegate_disabled_always_false() {
        assert!(!should_delegate(false, "https://home.example.com"));
    }

    #[test]
    fn test_should_delegate_empty_url() {
        assert!(!should_delegate(true, ""));
    }

    #[test]
    fn test_should_delegate_localhost_url() {
        assert!(!should_delegate(true, "http://localhost:8080"));
    }

    #[test]
    fn test_should_delegate_loopback_url() {
        assert!(!should_delegate(true, "http://127.0.0.1:8080"));
    }

    #[test]
    fn test_should_delegate_public_url() {
        assert!(should_delegate(true, "https://mecris.example.com"));
    }

    #[test]
    fn test_should_delegate_trailing_slash_public_url() {
        assert!(should_delegate(true, "https://home.example.com/"));
    }

    // --- parse_forecast_count ---

    #[test]
    fn test_parse_forecast_count_object_form() {
        let v = serde_json::json!({ "count": 42 });
        assert_eq!(parse_forecast_count(&v), 42);
    }

    #[test]
    fn test_parse_forecast_count_raw_integer() {
        let v = serde_json::json!(17);
        assert_eq!(parse_forecast_count(&v), 17);
    }

    #[test]
    fn test_parse_forecast_count_missing_falls_back_to_zero() {
        let v = serde_json::json!({});
        assert_eq!(parse_forecast_count(&v), 0);
    }

    #[test]
    fn test_parse_forecast_count_null_falls_back_to_zero() {
        let v = serde_json::json!(null);
        assert_eq!(parse_forecast_count(&v), 0);
    }

    // --- twilio helpers ---

    #[test]
    fn test_build_twilio_url_contains_account_sid() {
        let url = build_twilio_url("AC1234567890abcdef");
        assert!(url.contains("AC1234567890abcdef"));
        assert!(url.starts_with("https://api.twilio.com/"));
    }

    #[test]
    fn test_build_twilio_body_contains_fields() {
        let body = build_twilio_body("+15551234567", "+15559876543", "Hello!");
        assert!(body.contains("From="));
        assert!(body.contains("To="));
        assert!(body.contains("Body="));
    }

    #[test]
    fn test_encode_basic_auth_non_empty() {
        let encoded = encode_basic_auth("user", "pass");
        assert!(!encoded.is_empty());
    }

    #[test]
    fn test_encode_basic_auth_known_value() {
        // base64("user:pass") == "dXNlcjpwYXNz"
        let encoded = encode_basic_auth("user", "pass");
        assert_eq!(encoded, "dXNlcjpwYXNz");
    }

    // --- build_sms_request_parts ---

    #[test]
    fn test_build_sms_request_parts_url_contains_account_sid() {
        let (url, _, _) = build_sms_request_parts("AC1234567890abcdef", "tok", "+15550001111", "+15559876543", "Hello!");
        assert!(url.contains("AC1234567890abcdef"), "URL should contain account SID");
        assert!(url.starts_with("https://api.twilio.com/"), "URL should start with Twilio base");
    }

    #[test]
    fn test_build_sms_request_parts_body_contains_fields() {
        let (_, body, _) = build_sms_request_parts("ACtest", "tok", "+15550001111", "+15559876543", "Go walk!");
        assert!(body.contains("From="), "body should have From field");
        assert!(body.contains("To="), "body should have To field");
        assert!(body.contains("Body="), "body should have Body field");
    }

    #[test]
    fn test_build_sms_request_parts_auth_is_basic() {
        let (_, _, auth) = build_sms_request_parts("ACtest", "mysecret", "+1", "+2", "msg");
        assert!(auth.starts_with("Basic "), "Authorization header should start with 'Basic '");
        assert!(auth.len() > 6, "Authorization header should be non-trivial");
    }

    #[test]
    fn test_build_sms_request_parts_auth_encodes_sid_and_token() {
        // Basic base64("ACsid:ACtoken") should be consistent with encode_basic_auth
        let (_, _, auth) = build_sms_request_parts("ACsid", "ACtoken", "+1", "+2", "msg");
        let expected = format!("Basic {}", encode_basic_auth("ACsid", "ACtoken"));
        assert_eq!(auth, expected);
    }

    // --- arabic_completions ---

    #[test]
    fn test_arabic_completions_zero() {
        assert_eq!(arabic_completions(0), 0);
    }

    #[test]
    fn test_arabic_completions_one_card() {
        // 12 points → 1 card
        assert_eq!(arabic_completions(12), 1);
    }

    #[test]
    fn test_arabic_completions_partial_card_truncates() {
        // 11 points → 0 cards (truncated, not rounded)
        assert_eq!(arabic_completions(11), 0);
    }

    #[test]
    fn test_arabic_completions_large_session() {
        // 120 points → 10 cards
        assert_eq!(arabic_completions(120), 10);
    }

    // --- is_within_reminder_window ---

    #[test]
    fn test_reminder_window_active_morning() {
        // 9 AM is well within the active window
        assert!(is_within_reminder_window(9));
    }

    #[test]
    fn test_reminder_window_active_afternoon() {
        // 15 (3 PM) is within the active window
        assert!(is_within_reminder_window(15));
    }

    #[test]
    fn test_reminder_window_active_boundary_start() {
        // 8 AM is the inclusive start of the window
        assert!(is_within_reminder_window(8));
    }

    #[test]
    fn test_reminder_window_sleep_boundary_end() {
        // 20 (8 PM) is the exclusive end — should NOT send
        assert!(!is_within_reminder_window(20));
    }

    #[test]
    fn test_reminder_window_sleep_midnight() {
        // Midnight is in the sleep window
        assert!(!is_within_reminder_window(0));
    }

    #[test]
    fn test_reminder_window_sleep_early_morning() {
        // 7 AM is still the sleep window
        assert!(!is_within_reminder_window(7));
    }

    #[test]
    fn test_reminder_window_sleep_late_night() {
        // 23 (11 PM) is in the sleep window
        assert!(!is_within_reminder_window(23));
    }

    // --- is_below_step_threshold ---

    #[test]
    fn test_step_threshold_below() {
        // 1999 steps → should remind
        assert!(is_below_step_threshold(1999, 2000));
    }

    #[test]
    fn test_step_threshold_at_goal() {
        // Exactly 2000 steps → goal met, do not remind
        assert!(!is_below_step_threshold(2000, 2000));
    }

    #[test]
    fn test_step_threshold_above_goal() {
        // 5000 steps → well above goal, do not remind
        assert!(!is_below_step_threshold(5000, 2000));
    }

    #[test]
    fn test_step_threshold_zero() {
        // 0 steps → definitely should remind
        assert!(is_below_step_threshold(0, 2000));
    }

    // --- is_rate_limit_ok ---

    #[test]
    fn test_rate_limit_no_previous_message() {
        // No prior message → always ok to send
        assert!(is_rate_limit_ok(None));
    }

    #[test]
    fn test_rate_limit_too_recent() {
        // 239 minutes ago → too soon (minimum is 240)
        assert!(!is_rate_limit_ok(Some(239)));
    }

    #[test]
    fn test_rate_limit_exactly_at_boundary() {
        // 240 minutes ago → exactly at limit, ok to send
        assert!(is_rate_limit_ok(Some(240)));
    }

    #[test]
    fn test_rate_limit_long_gap() {
        // 300 minutes ago → well past limit
        assert!(is_rate_limit_ok(Some(300)));
    }

    // --- should_dispatch_reminder ---

    #[test]
    fn test_should_dispatch_all_conditions_met() {
        // Active hour, low steps, no prior message → dispatch
        assert!(should_dispatch_reminder(10, 500, None));
    }

    #[test]
    fn test_should_dispatch_wrong_hour_blocks() {
        // Sleep window: suppress even with low steps and no prior message
        assert!(!should_dispatch_reminder(2, 500, None));
    }

    #[test]
    fn test_should_dispatch_goal_met_blocks() {
        // Step goal reached: suppress even in active window
        assert!(!should_dispatch_reminder(10, 2000, None));
    }

    #[test]
    fn test_should_dispatch_rate_limited_blocks() {
        // Too recent: suppress even with low steps in active window
        assert!(!should_dispatch_reminder(10, 500, Some(15)));
    }

    // --- is_weather_ok_for_walk ---

    #[test]
    fn test_is_it_dark_daytime() {
        // Sunrise 6am (21600), Sunset 6pm (64800), Now 12pm (43200)
        assert!(!is_it_dark(43200, 21600, 64800));
    }

    #[test]
    fn test_is_it_dark_before_sunrise() {
        // Sunrise 6am (21600), Now 5am (18000)
        assert!(is_it_dark(18000, 21600, 64800));
    }

    #[test]
    fn test_is_it_dark_after_sunset() {
        // Sunset 6pm (64800), Now 7pm (68400)
        assert!(is_it_dark(68400, 21600, 64800));
    }

    #[test]
    fn test_weather_ok_clear() {
        assert!(is_weather_ok_for_walk("Clear"));
    }

    #[test]
    fn test_weather_ok_clouds() {
        assert!(is_weather_ok_for_walk("Clouds"));
    }

    #[test]
    fn test_weather_bad_rain() {
        assert!(!is_weather_ok_for_walk("Rain"));
    }

    #[test]
    fn test_weather_bad_thunderstorm() {
        assert!(!is_weather_ok_for_walk("Thunderstorm"));
    }

    #[test]
    fn test_weather_bad_snow() {
        assert!(!is_weather_ok_for_walk("Snow"));
    }

    #[test]
    fn test_weather_bad_drizzle() {
        assert!(!is_weather_ok_for_walk("Drizzle"));
    }

    #[test]
    fn test_weather_bad_atmosphere() {
        // "Atmosphere" covers fog, haze, mist — conservative: skip walk
        assert!(!is_weather_ok_for_walk("Atmosphere"));
    }

    #[test]
    fn test_weather_unknown_is_false() {
        // Unknown / empty defaults to false (conservative)
        assert!(!is_weather_ok_for_walk(""));
        assert!(!is_weather_ok_for_walk("Tornado"));
    }

    // --- resolve_lat_lon ---

    #[test]
    fn test_resolve_lat_lon_user_preferred() {
        // Per-user coordinates take priority over global Spin vars
        let result = resolve_lat_lon(Some("51.5074"), Some("-0.1278"), Some("40.7128"), Some("-74.0060"));
        assert_eq!(result, Some((51.5074, -0.1278)));
    }

    #[test]
    fn test_resolve_lat_lon_global_fallback() {
        // No per-user location → fall back to global Spin variables
        let result = resolve_lat_lon(None, None, Some("40.7128"), Some("-74.0060"));
        assert_eq!(result, Some((40.7128, -74.0060)));
    }

    #[test]
    fn test_resolve_lat_lon_parse_error_fallback() {
        // Unparseable per-user coords → fall back to global
        let result = resolve_lat_lon(Some("not-a-float"), Some("-0.1278"), Some("40.7128"), Some("-74.0060"));
        assert_eq!(result, Some((40.7128, -74.0060)));
    }

    #[test]
    fn test_resolve_lat_lon_none_when_no_coords() {
        // No per-user and no global → None (skip weather check gracefully)
        let result = resolve_lat_lon(None, None, None, None);
        assert_eq!(result, None);
    }

    // --- aggregate_step_count ---

    #[test]
    fn test_aggregate_step_count_empty() {
        assert_eq!(aggregate_step_count(&[]), 0);
    }

    #[test]
    fn test_aggregate_step_count_single() {
        assert_eq!(aggregate_step_count(&["1500".to_string()]), 1500);
    }

    #[test]
    fn test_aggregate_step_count_multiple() {
        assert_eq!(aggregate_step_count(&["1000".to_string(), "500".to_string(), "200".to_string()]), 200);
    }

    #[test]
    fn test_aggregate_step_count_skips_invalid() {
        assert_eq!(aggregate_step_count(&["bad".to_string(), "800".to_string()]), 800);
    }

    #[test]
    fn test_aggregate_step_count_ordering_contract() {
        // The SQL query feeding this function uses ORDER BY start_time ASC, so
        // the last element in the slice is the most recently recorded step count.
        // This test documents that contract and guards against removing ORDER BY.
        // Regression test for kingdonb/mecris#180 (non-deterministic Rust DB query).
        let sessions_asc_order = [
            "500".to_string(),  // earliest session today
            "1200".to_string(), // mid-day session
            "3000".to_string(), // most recent session
        ];
        assert_eq!(aggregate_step_count(&sessions_asc_order), 3000);
    }

    // --- local_hour_from_timezone ---

    #[test]
    fn test_local_hour_utc_stays_same() {
        // 2026-04-11 14:00:00 UTC → UTC hour 14
        let dt = chrono::DateTime::parse_from_rfc3339("2026-04-11T14:00:00+00:00")
            .unwrap()
            .with_timezone(&chrono::Utc);
        assert_eq!(local_hour_from_timezone("UTC", &dt), 14);
    }

    #[test]
    fn test_local_hour_america_new_york_offset() {
        // 2026-04-11 14:00:00 UTC → EDT = UTC-4 → local hour 10
        let dt = chrono::DateTime::parse_from_rfc3339("2026-04-11T14:00:00+00:00")
            .unwrap()
            .with_timezone(&chrono::Utc);
        assert_eq!(local_hour_from_timezone("America/New_York", &dt), 10);
    }

    #[test]
    fn test_local_hour_unknown_timezone_falls_back_to_utc() {
        let dt = chrono::DateTime::parse_from_rfc3339("2026-04-11T10:00:00+00:00")
            .unwrap()
            .with_timezone(&chrono::Utc);
        assert_eq!(local_hour_from_timezone("Not/ATimezone", &dt), 10);
    }

    // --- minutes_since_last_reminder ---

    #[test]
    fn test_minutes_since_last_none_input() {
        assert_eq!(minutes_since_last_reminder(None, 12345678), None);
    }

    #[test]
    fn test_minutes_since_last_exactly_30_min() {
        // 2026-01-01T00:00:00Z = 1767225600
        assert_eq!(minutes_since_last_reminder(Some("2026-01-01T00:00:00+00:00"), 1767225600 + 1800), Some(30));
    }

    #[test]
    fn test_minutes_since_last_1_hour() {
        assert_eq!(minutes_since_last_reminder(Some("2026-01-01T00:00:00+00:00"), 1767225600 + 3600), Some(60));
    }

    #[test]
    fn test_minutes_since_last_unparseable_returns_none() {
        assert_eq!(minutes_since_last_reminder(Some("not-a-timestamp"), 99999), None);
    }

    // --- is_affirmative_response ---

    #[test]
    fn test_affirmative_yes_uppercase() {
        assert!(is_affirmative_response("Body=YES&From=%2B15551234567"));
    }

    #[test]
    fn test_affirmative_yes_lowercase() {
        assert!(is_affirmative_response("Body=yes&From=%2B15551234567"));
    }

    #[test]
    fn test_affirmative_y() {
        assert!(is_affirmative_response("Body=Y&From=%2B15551234567"));
    }

    #[test]
    fn test_affirmative_done() {
        assert!(is_affirmative_response("Body=DONE&From=%2B15551234567"));
    }

    #[test]
    fn test_affirmative_ok() {
        assert!(is_affirmative_response("Body=OK&From=%2B15551234567"));
    }

    #[test]
    fn test_affirmative_no_is_false() {
        assert!(!is_affirmative_response("Body=NO&From=%2B15551234567"));
    }

    #[test]
    fn test_affirmative_empty_body_is_false() {
        assert!(!is_affirmative_response(""));
    }

    #[test]
    fn test_affirmative_missing_body_field_is_false() {
        assert!(!is_affirmative_response("From=%2B15551234567&To=%2B15559876543"));
    }

    // --- validate_twilio_signature ---

    #[test]
    fn test_twilio_signature_valid_twilio_example() {
        // Known test vector: Twilio documentation example
        // python: hmac.new(b"12345", b"https://mycompany.com/myapp.php?foo=1&bar=2CallSidCA1234567890ABCDECaller+14158675310Digits1234From+14158675310To+18005551212", hashlib.sha1)
        let auth_token = "12345";
        let url = "https://mycompany.com/myapp.php?foo=1&bar=2";
        let params: Vec<(String, String)> = vec![
            ("CallSid".to_string(), "CA1234567890ABCDE".to_string()),
            ("Caller".to_string(), "+14158675310".to_string()),
            ("Digits".to_string(), "1234".to_string()),
            ("From".to_string(), "+14158675310".to_string()),
            ("To".to_string(), "+18005551212".to_string()),
        ];
        let signature = "GvWf1cFY/Q7PnoempGyD5oXAezc=";
        assert!(validate_twilio_signature(auth_token, url, &params, signature));
    }

    #[test]
    fn test_twilio_signature_empty_params() {
        // python: base64.b64encode(hmac.new(b"secret", b"https://example.com/hook", hashlib.sha1).digest())
        let signature = "73HVjq6EFDqxMRzMDoRH96HHWAM=";
        assert!(validate_twilio_signature("secret", "https://example.com/hook", &[], signature));
    }

    #[test]
    fn test_twilio_signature_wrong_token_fails() {
        assert!(!validate_twilio_signature("wrongtoken", "https://example.com/hook", &[], "invalid=="));
    }

    #[test]
    fn test_twilio_signature_wrong_sig_fails() {
        assert!(!validate_twilio_signature("secret", "https://example.com/hook", &[], "WRONGSIG=="));
    }

    // --- extract_from_number ---

    #[test]
    fn test_extract_from_number_present() {
        assert_eq!(
            extract_from_number("Body=YES&From=%2B15551234567"),
            Some("+15551234567".to_string())
        );
    }

    #[test]
    fn test_extract_from_number_absent() {
        assert_eq!(extract_from_number("Body=YES&To=%2B15551234567"), None);
    }

    #[test]
    fn test_extract_from_number_empty_body() {
        assert_eq!(extract_from_number(""), None);
    }

    // --- build_beeminder_datapoint_body ---

    #[test]
    fn test_build_beeminder_datapoint_body_basic() {
        let body = build_beeminder_datapoint_body("mytoken", 1.0, "walk done");
        assert!(body.starts_with("auth_token=mytoken&value=1&comment="));
        assert!(body.contains("walk%20done"));
    }

    #[test]
    fn test_build_beeminder_datapoint_body_zero_value() {
        let body = build_beeminder_datapoint_body("tok", 0.0, "");
        assert_eq!(body, "auth_token=tok&value=0&comment=");
    }

    #[test]
    fn test_build_beeminder_datapoint_body_fractional_value() {
        let body = build_beeminder_datapoint_body("tok", 1.5, "morning walk");
        assert!(body.contains("value=1.5"));
        assert!(body.contains("morning%20walk"));
    }

    // --- normalize_phone / phones_match ---

    #[test]
    fn test_normalize_phone_strips_formatting() {
        assert_eq!(normalize_phone("+1 (555) 123-4567"), "+15551234567");
    }

    #[test]
    fn test_normalize_phone_plain_e164() {
        assert_eq!(normalize_phone("+15551234567"), "+15551234567");
    }

    #[test]
    fn test_normalize_phone_empty() {
        assert_eq!(normalize_phone(""), "");
    }

    #[test]
    fn test_phones_match_identical_e164() {
        assert!(phones_match("+15551234567", "+15551234567"));
    }

    #[test]
    fn test_phones_match_formatted_vs_e164() {
        assert!(phones_match("+1 (555) 123-4567", "+15551234567"));
    }

    #[test]
    fn test_phones_match_different_numbers() {
        assert!(!phones_match("+15551234567", "+15559876543"));
    }

    #[test]
    fn test_phones_match_empty_a_is_false() {
        assert!(!phones_match("", "+15551234567"));
    }

    #[test]
    fn test_phones_match_empty_b_is_false() {
        assert!(!phones_match("+15551234567", ""));
    }

    #[test]
    fn test_phones_match_both_empty_is_false() {
        assert!(!phones_match("", ""));
    }

    // --- android_client_is_active ---

    #[test]
    fn test_android_active_no_heartbeat_returns_false() {
        // No heartbeat recorded → cloud may send
        assert!(!android_client_is_active(None));
    }

    #[test]
    fn test_android_active_fresh_heartbeat_blocks_cloud() {
        // Android heartbeat 30 minutes ago → suppress cloud nag
        assert!(android_client_is_active(Some(30)));
    }

    #[test]
    fn test_android_active_exactly_239_minutes_blocks_cloud() {
        // 239 minutes → still within 4-hour window → active
        assert!(android_client_is_active(Some(239)));
    }

    #[test]
    fn test_android_active_exactly_240_minutes_allows_cloud() {
        // 240 minutes = exactly 4 hours → threshold crossed → cloud may send
        assert!(!android_client_is_active(Some(240)));
    }

    #[test]
    fn test_android_active_very_stale_allows_cloud() {
        // 480 minutes = 8 hours → well past threshold → cloud may send
        assert!(!android_client_is_active(Some(480)));
    }

    // --- internal_api_key_ok ---

    #[test]
    fn test_internal_api_key_no_key_configured_allows_all() {
        // If no key is configured (empty string), any caller is allowed — backwards compatible.
        assert!(internal_api_key_ok("", None));
        assert!(internal_api_key_ok("", Some("anything")));
    }

    #[test]
    fn test_internal_api_key_correct_key_allows() {
        assert!(internal_api_key_ok("supersecret", Some("supersecret")));
    }

    #[test]
    fn test_internal_api_key_wrong_key_blocks() {
        assert!(!internal_api_key_ok("supersecret", Some("wrongkey")));
    }

    #[test]
    fn test_internal_api_key_missing_header_blocks() {
        assert!(!internal_api_key_ok("supersecret", None));
    }

    // --- get_modality_status_string ---

    #[test]
    fn test_modality_status_leader() {
        assert_eq!(get_modality_status_string("leader", 1), "healthy");
        assert_eq!(get_modality_status_string("leader", 3), "degraded");
        assert_eq!(get_modality_status_string("leader", 10), "offline");
    }

    #[test]
    fn test_modality_status_android() {
        assert_eq!(get_modality_status_string("android_client", 15), "healthy");
        assert_eq!(get_modality_status_string("android_client", 45), "degraded");
        assert_eq!(get_modality_status_string("android_client", 300), "offline");
    }

    #[test]
    fn test_modality_status_akamai() {
        assert_eq!(get_modality_status_string("akamai_functions", 120), "healthy");
        assert_eq!(get_modality_status_string("akamai_functions", 200), "degraded");
        assert_eq!(get_modality_status_string("akamai_functions", 300), "offline");
    }

    #[test]
    fn test_modality_status_fermyon() {
        assert_eq!(get_modality_status_string("fermyon_cloud", 2), "healthy");
        assert_eq!(get_modality_status_string("fermyon_cloud", 10), "degraded");
        assert_eq!(get_modality_status_string("fermyon_cloud", 20), "offline");
    }

    #[test]
    fn test_modality_status_unknown() {
        assert_eq!(get_modality_status_string("unknown_role", 1), "unknown");
    }

    // --- add_cors ---

    #[test]
    fn test_add_cors_preserves_status_and_headers() {
        let resp = Response::builder()
            .status(201)
            .header("content-type", "application/json")
            .body("{\"ok\":true}")
            .build();
        
        let cors_resp = add_cors(resp);
        
        assert_eq!(*cors_resp.status(), 201);
        
        let headers: std::collections::HashMap<String, String> = cors_resp.headers()
            .map(|(k, v)| (k.to_string(), std::str::from_utf8(v.as_ref()).unwrap().to_string()))
            .collect();
            
        assert_eq!(headers.get("content-type").unwrap(), "application/json");
        assert_eq!(headers.get("access-control-allow-origin").unwrap(), "*");
        assert_eq!(std::str::from_utf8(cors_resp.body()).unwrap(), "{\"ok\":true}");
    }
}
