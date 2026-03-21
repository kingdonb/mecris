use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use spin_sdk::{
    http::{IntoResponse, Request, Response},
    http_component,
    pg::{Connection, ParameterValue, DbValue},
    variables,
};
use spin_cron_sdk::{cron_component, Metadata};

#[cron_component]
async fn handle_cron(_metadata: Metadata) -> anyhow::Result<()> {
    println!("Spin Cron: Starting failover sync check...");
    let db_url = match variables::get("db_url") {
        Ok(url) if !url.is_empty() => url,
        _ => {
            eprintln!("Missing db_url variable");
            return Ok(());
        }
    };
    
    // We can reuse the logic from handle_failover_sync, 
    // but handle_failover_sync returns a Response.
    // Let's refactor the core logic.
    match perform_failover_sync(&db_url).await {
        Ok(msg) => println!("Spin Cron: {}", msg),
        Err(e) => eprintln!("Spin Cron Error: {:?}", e),
    }

    Ok(())
}
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
use jwt_simple::prelude::*;
use spin_sdk::key_value::Store;

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

#[derive(Deserialize, Debug)]
struct OidcConfig {
    jwks_uri: String,
}

async fn get_jwks() -> anyhow::Result<Jwks> {
    let store = Store::open_default()?;
    
    // Check cache
    if let Ok(cached) = store.get("jwks") {
        if let Some(bytes) = cached {
            if let Ok(jwks) = serde_json::from_slice(&bytes) {
                return Ok(jwks);
            }
        }
    }

    let discovery_url = variables::get("oidc_discovery_url")?;
    let req = Request::get(&discovery_url).build();
    let res: Response = spin_sdk::http::send(req).await?;
    let config: OidcConfig = serde_json::from_slice(res.body())?;

    let req = Request::get(&config.jwks_uri).build();
    let res: Response = spin_sdk::http::send(req).await?;
    let jwks: Jwks = serde_json::from_slice(res.body())?;

    // Cache for 1 hour (Spin KV doesn't support TTL natively, we'd need a timestamp)
    let _ = store.set("jwks", &serde_json::to_vec(&jwks)?);

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

#[derive(Deserialize, Debug, Serialize)]
struct JwtClaims {
    sub: String,
    exp: u64,
    iss: Option<String>,
    aud: Option<String>,
}

use aes_gcm::{
    aead::{Aead, KeyInit},
    Aes256Gcm, Nonce
};

async fn decrypt_token(encrypted_hex: &str) -> anyhow::Result<String> {
    let key_str = variables::get("master_encryption_key")?;
    let key_bytes = hex::decode(key_str)?;
    let cipher = Aes256Gcm::new_from_slice(&key_bytes)?;

    let encrypted_bytes = hex::decode(encrypted_hex)?;
    if encrypted_bytes.len() < 12 {
        return Err(anyhow::anyhow!("Invalid encrypted token length"));
    }

    let nonce = Nonce::from_slice(&encrypted_bytes[..12]);
    let ciphertext = &encrypted_bytes[12..];

    let decrypted_bytes = cipher.decrypt(nonce, ciphertext)
        .map_err(|e| anyhow::anyhow!("Decryption failed: {:?}", e))?;

    Ok(String::from_utf8(decrypted_bytes)?)
}

#[allow(dead_code)]
async fn encrypt_token(plain_text: &str) -> anyhow::Result<String> {
    let key_str = variables::get("master_encryption_key")?;
    let key_bytes = hex::decode(key_str)?;
    let cipher = Aes256Gcm::new_from_slice(&key_bytes)?;

    let mut nonce_bytes = [0u8; 12];
    // In a real WASM environment, we'd need a source of randomness.
    // Spin SDK doesn't provide it directly in all versions, 
    // but getrandom crate with "js" or "wasi" feature works.
    // For now, we'll use a fixed nonce (INSECURE) or better, 
    // ensure the user provides one if possible.
    // Actually, we can use the current time as a pseudo-nonce for now 
    // IF we don't have getrandom.
    // Let's assume getrandom works since we are in wasm32-wasip1.
    getrandom::getrandom(&mut nonce_bytes)?;
    let nonce = Nonce::from_slice(&nonce_bytes);

    let ciphertext = cipher.encrypt(nonce, plain_text.as_bytes())
        .map_err(|e| anyhow::anyhow!("Encryption failed: {:?}", e))?;

    let mut combined = nonce_bytes.to_vec();
    combined.extend(ciphertext);

    Ok(hex::encode(combined))
}

async fn extract_user_id(auth_header: Option<&spin_sdk::http::HeaderValue>) -> Option<String> {
    let header_val = std::str::from_utf8(auth_header?.as_ref()).ok()?;
    if !header_val.starts_with("Bearer ") {
        return None;
    }
    let token = &header_val[7..];

    // 1. Fetch JWKS
    let jwks = get_jwks().await.ok()?;

    // 2. Decode header to get kid
    // jwt-simple doesn't expose header easily in unverified parse, 
    // we can use manual decode for kid
    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() != 3 { return None; }
    let header_bytes = URL_SAFE_NO_PAD.decode(parts[0]).ok()?;
    let header: serde_json::Value = serde_json::from_slice(&header_bytes).ok()?;
    let kid = header.get("kid")?.as_str()?;

    // 3. Find key
    let key = jwks.keys.iter().find(|k| k.kid == kid)?;

    // 4. Verify signature
    if key.kty == "RSA" && key.alg == "RS256" {
        let n_bytes = URL_SAFE_NO_PAD.decode(&key.n).ok()?;
        let e_bytes = URL_SAFE_NO_PAD.decode(&key.e).ok()?;
        let public_key = RS256PublicKey::from_components(&n_bytes, &e_bytes).ok()?;
        
        let options = VerificationOptions::default();
        // options.allowed_issuers = Some(HashSet::from(["https://metnoom.urmanac.com".to_string()]));
        
        let claims = public_key.verify_token::<JwtClaims>(token, Some(options)).ok()?;
        return Some(claims.custom.sub);
    }

    None
}

#[http_component]
async fn handle_sync_service(req: Request) -> anyhow::Result<impl IntoResponse> {
    let path = req.path();
    
    if path == "/walks" {
        if req.method() != &spin_sdk::http::Method::Post {
            return Ok(Response::builder().status(405).body("Method Not Allowed").build());
        }
        return handle_walks_post(req).await;
    } else if path == "/budget" {
        if req.method() != &spin_sdk::http::Method::Get {
            return Ok(Response::builder().status(405).body("Method Not Allowed").build());
        }
        return handle_budget_get(req).await;
    } else if path == "/languages" {
        if req.method() != &spin_sdk::http::Method::Get {
            return Ok(Response::builder().status(405).body("Method Not Allowed").build());
        }
        return handle_languages_get(req).await;
    } else if path == "/languages/multiplier" {
        if req.method() != &spin_sdk::http::Method::Post {
            return Ok(Response::builder().status(405).body("Method Not Allowed").build());
        }
        return handle_multiplier_post(req).await;
    } else if path == "/health" {
        if req.method() != &spin_sdk::http::Method::Get {
            return Ok(Response::builder().status(405).body("Method Not Allowed").build());
        }
        return handle_health_get(req).await;
    } else if path == "/heartbeat" {
        if req.method() != &spin_sdk::http::Method::Post {
            return Ok(Response::builder().status(405).body("Method Not Allowed").build());
        }
        return handle_heartbeat_post(req).await;
    } else if path == "/internal/failover-sync" {
        if req.method() != &spin_sdk::http::Method::Post && req.method() != &spin_sdk::http::Method::Get {
            return Ok(Response::builder().status(405).body("Method Not Allowed").build());
        }
        return handle_failover_sync(req).await;
    }
    
    Ok(Response::builder().status(404).body("Not Found").build())
}

async fn handle_failover_sync(_req: Request) -> anyhow::Result<Response> {
    let db_url = match variables::get("db_url") {
        Ok(url) if !url.is_empty() => url,
        _ => return Ok(Response::builder().status(500).body("Missing db_url").build())
    };

    match perform_failover_sync(&db_url).await {
        Ok(msg) => {
            let status = if msg.contains("skipped") { "skipped" } else { "active" };
            let resp = StatusResponse {
                status: status.to_string(),
                message: msg,
            };
            Ok(Response::builder()
                .status(200)
                .header("content-type", "application/json")
                .body(serde_json::to_string(&resp).unwrap())
                .build())
        },
        Err(e) => {
            let resp = StatusResponse {
                status: "error".to_string(),
                message: format!("Failover sync failed: {:?}", e),
            };
            Ok(Response::builder()
                .status(500)
                .header("content-type", "application/json")
                .body(serde_json::to_string(&resp).unwrap())
                .build())
        }
    }
}

async fn perform_failover_sync(db_url: &str) -> anyhow::Result<String> {
    let connection = Connection::open(db_url)?;

    let query = "SELECT (heartbeat > NOW() - INTERVAL '90 seconds') as is_active FROM scheduler_election WHERE role = 'leader' LIMIT 1";
    let row_set = connection.query(query, &[])?;

    let mut is_leader_active = false;

    if !row_set.rows.is_empty() {
        if let DbValue::Boolean(active) = &row_set.rows[0][0] {
            is_leader_active = *active;
        }
    }

    if is_leader_active {
        return Ok("Home server is active. Failover mode skipped.".to_string());
    }

    // --- FAILOVER MODE ACTIVATED ---
    println!("FAILOVER MODE ACTIVE: Home server heartbeat is stale or missing.");
    
    // Scrape Clozemaster and push to Neon
    run_clozemaster_scraper(db_url).await
}

// Helper for managing cookies across requests
struct CookieJar {
    cookies: HashMap<String, String>,
}

impl CookieJar {
    fn new() -> Self {
        Self { cookies: HashMap::new() }
    }

    fn update_from_headers(&mut self, response: &Response) {
        for (name, value) in response.headers() {
            if name.to_string().to_lowercase() == "set-cookie" {
                if let Ok(c) = std::str::from_utf8(value.as_ref()) {
                    // Do not split by comma - each Set-Cookie header is one entry.
                    let part = c.split(';').next().unwrap_or("");
                    if let Some(pos) = part.find('=') {
                        let k = part[..pos].trim().to_string();
                        let v = part[pos+1..].trim().to_string();
                        if !k.is_empty() {
                            self.cookies.insert(k, v);
                        }
                    }
                }
            }
        }
    }

    fn to_header_value(&self) -> String {
        self.cookies.iter()
            .map(|(k, v)| format!("{}={}", k, v))
            .collect::<Vec<_>>()
            .join("; ")
    }
}

async fn run_clozemaster_scraper(db_url: &str) -> anyhow::Result<String> {
    let email = variables::get("clozemaster_email").unwrap_or_default();
    let password = variables::get("clozemaster_password").unwrap_or_default();
    
    if email.is_empty() || password.is_empty() {
        return Err(anyhow::anyhow!("Missing clozemaster credentials"));
    }

    let user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36";
    let mut cookie_jar = CookieJar::new();

    println!("Failover worker: Starting Clozemaster sync...");
    
    // 1. GET login to grab CSRF token
    let login_get_req = Request::get("https://www.clozemaster.com/login")
        .header("User-Agent", user_agent)
        .header("Upgrade-Insecure-Requests", "1")
        .build();
        
    let login_get_res: Response = spin_sdk::http::send(login_get_req).await?;
    cookie_jar.update_from_headers(&login_get_res);
    
    let body_bytes = login_get_res.body();
    let body_str = String::from_utf8_lossy(body_bytes);
    
    // Extract CSRF token
    let csrf_re = regex::Regex::new(r#"name="authenticity_token" value="([^"]+)""#).unwrap();
    let csrf_token = match csrf_re.captures(&body_str) {
        Some(caps) => caps.get(1).unwrap().as_str().to_string(),
        None => return Err(anyhow::anyhow!("Could not find CSRF token on login page")),
    };
    
    // Detect login field name (user[login] or user[email])
    let user_field = if body_str.contains("name=\"user[login]\"") {
        "user[login]"
    } else {
        "user[email]"
    };

    // 2. POST login
    let login_body = format!(
        "{}={}&user%5Bpassword%5D={}&authenticity_token={}&commit=Log+In",
        urlencoding::encode(user_field),
        urlencoding::encode(&email),
        urlencoding::encode(&password),
        urlencoding::encode(&csrf_token)
    );
    
    let login_post_req = Request::post("https://www.clozemaster.com/login", login_body)
        .header("User-Agent", user_agent)
        .header("Content-Type", "application/x-www-form-urlencoded")
        .header("Cookie", cookie_jar.to_header_value())
        .header("Referer", "https://www.clozemaster.com/login")
        .header("Upgrade-Insecure-Requests", "1")
        .build();
        
    let login_post_res: Response = spin_sdk::http::send(login_post_req).await?;
    cookie_jar.update_from_headers(&login_post_res);

    let status = *login_post_res.status();
    
    // On success Clozemaster returns 302 to dashboard. 
    if status == 200 {
        let post_body = String::from_utf8_lossy(login_post_res.body());
        if post_body.contains("Login") || post_body.contains("Invalid") {
            return Err(anyhow::anyhow!("Login failed: still on login page after POST"));
        }
    } else if status < 300 || status >= 400 {
        return Err(anyhow::anyhow!("Login POST failed with status: {}", status));
    }

    // 3. GET dashboard (with redirect following)
    let mut current_url = "https://www.clozemaster.com/dashboard".to_string();
    let mut dash_body = String::new();
    
    for _ in 0..3 {
        let dash_req = Request::get(&current_url)
            .header("User-Agent", user_agent)
            .header("Cookie", cookie_jar.to_header_value())
            .header("Referer", "https://www.clozemaster.com/login")
            .header("Upgrade-Insecure-Requests", "1")
            .header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8")
            .header("Accept-Language", "en-US,en;q=0.9")
            .header("Cache-Control", "max-age=0")
            .build();
            
        let dash_res: Response = spin_sdk::http::send(dash_req).await?;
        let status = *dash_res.status();
        cookie_jar.update_from_headers(&dash_res);
        
        if status >= 300 && status < 400 {
            if let Some(loc) = dash_res.header("location") {
                let loc_str = String::from_utf8_lossy(loc.as_ref()).to_string();
                if loc_str.starts_with('/') {
                    current_url = format!("https://www.clozemaster.com{}", loc_str);
                } else {
                    current_url = loc_str;
                }
                continue;
            }
        }
        
        dash_body = String::from_utf8_lossy(dash_res.body()).to_string();
        break;
    }
    
    // Check if we actually got the dashboard
    if !dash_body.contains("DashboardV5") {
        if dash_body.contains("Login") {
            return Err(anyhow::anyhow!("Dashboard request redirected to login - session failed"));
        }
        return Err(anyhow::anyhow!("Could not find DashboardV5 in response - body size: {}", dash_body.len()));
    }
    
    // Extract fresh CSRF token from dashboard for enrichment API calls
    let csrf_meta_re = regex::Regex::new(r#"<meta[^>]+name=['"]csrf-token['"][^>]*content=['"]([^'"]+)['"]"#).unwrap();
    let dash_csrf_token = match csrf_meta_re.captures(&dash_body) {
        Some(caps) => caps.get(1).unwrap().as_str().to_string(),
        None => {
            let csrf_meta_re2 = regex::Regex::new(r#"<meta[^>]+content=['"]([^'"]+)['"][^>]*name=['"]csrf-token['"]"#).unwrap();
            match csrf_meta_re2.captures(&dash_body) {
                Some(caps) => caps.get(1).unwrap().as_str().to_string(),
                None => csrf_token.clone(),
            }
        },
    };

    let dash_div_re = regex::Regex::new(r#"(?s)<div[^>]+data-react-class=['"]DashboardV5['"][^>]*data-react-props=['"]([^'"]+)['"]"#).unwrap();
    let props_json_escaped = match dash_div_re.captures(&dash_body) {
        Some(caps) => caps.get(1).unwrap().as_str(),
        None => return Err(anyhow::anyhow!("Could not find DashboardV5 react props")),
    };
    
    let props_json = html_escape::decode_html_entities(props_json_escaped).to_string();
    
    let parsed: serde_json::Value = serde_json::from_str(&props_json)?;
    let pairings = parsed.get("languagePairings").and_then(|p| p.as_array()).ok_or_else(|| anyhow::anyhow!("No languagePairings found"))?;
    
    let mut arabic_count = 0;
    let mut greek_count = 0;
    let mut arabic_lp_id = 0;
    let mut greek_lp_id = 0;
    
    for pair in pairings {
        if let Some(slug) = pair.get("slug").and_then(|s| s.as_str()) {
            let count = pair.get("numReadyForReview").and_then(|n| n.as_i64()).unwrap_or(0);
            let id = pair.get("id").and_then(|n| n.as_i64()).unwrap_or(0);
            if slug == "ara-eng" {
                arabic_count = count;
                arabic_lp_id = id;
            } else if slug == "ell-eng" {
                greek_count = count;
                greek_lp_id = id;
            }
        }
    }

    let mut arabic_tomorrow = 0;
    let mut arabic_next_7 = 0;
    let mut greek_tomorrow = 0;
    let mut greek_next_7 = 0;

    async fn get_more_stats(lp_id: i64, lang_slug: &str, csrf: &str, cookie: &str, ua: &str) -> anyhow::Result<(i32, i32)> {
        if lp_id == 0 { return Ok((0, 0)); }
        let url = format!("https://www.clozemaster.com/api/v1/lp/{}/more-stats", lp_id);
        let req = Request::get(&url)
            .header("User-Agent", ua)
            .header("X-Requested-With", "XMLHttpRequest")
            .header("X-CSRF-Token", csrf)
            .header("Cookie", cookie)
            .header("Referer", &format!("https://www.clozemaster.com/l/{}", lang_slug))
            .header("Accept", "*/*")
            .header("Time-Zone-Offset-Hours", "-4")
            .build();
        let res: Response = spin_sdk::http::send(req).await?;
        if *res.status() != 200 { return Ok((0, 0)); }
        let body: serde_json::Value = serde_json::from_slice(res.body())?;
        let forecast = body.get("reviewForecast").and_then(|f| f.as_array());
        if let Some(f) = forecast {
            let tomorrow = f.get(0).and_then(|v| if v.is_number() { v.as_i64() } else { v.get("count").and_then(|c| c.as_i64()) }).unwrap_or(0) as i32;
            let next_7: i32 = f.iter().take(7).map(|v| if v.is_number() { v.as_i64() } else { v.get("count").and_then(|c| c.as_i64()) }.unwrap_or(0) as i32).sum();
            return Ok((tomorrow, next_7));
        }
        Ok((0, 0))
    }

    let current_cookies = cookie_jar.to_header_value();

    if arabic_lp_id != 0 {
        if let Ok((t, n7)) = get_more_stats(arabic_lp_id, "ara-eng", &dash_csrf_token, &current_cookies, user_agent).await {
            arabic_tomorrow = t;
            arabic_next_7 = n7;
        }
    }
    if greek_lp_id != 0 {
        if let Ok((t, n7)) = get_more_stats(greek_lp_id, "ell-eng", &dash_csrf_token, &current_cookies, user_agent).await {
            greek_tomorrow = t;
            greek_next_7 = n7;
        }
    }
    
    // 5. Update Neon
    let connection = Connection::open(db_url)?;
    
    let update_query = "
        INSERT INTO language_stats (language_name, current_reviews, tomorrow_reviews, next_7_days_reviews)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (language_name) DO UPDATE SET
            current_reviews = EXCLUDED.current_reviews,
            tomorrow_reviews = EXCLUDED.tomorrow_reviews,
            next_7_days_reviews = EXCLUDED.next_7_days_reviews,
            last_updated = CURRENT_TIMESTAMP
    ";
    
    let _ = connection.execute(update_query, &[ParameterValue::Str("ARABIC".to_string()), ParameterValue::Int32(arabic_count as i32), ParameterValue::Int32(arabic_tomorrow), ParameterValue::Int32(arabic_next_7)]);
    let _ = connection.execute(update_query, &[ParameterValue::Str("GREEK".to_string()), ParameterValue::Int32(greek_count as i32), ParameterValue::Int32(greek_tomorrow), ParameterValue::Int32(greek_next_7)]);
    
    Ok(format!("Scraped Arabic: {} (+{}), Greek: {} (+{})", arabic_count, arabic_tomorrow, greek_count, greek_tomorrow))
}


async fn handle_health_get(_req: Request) -> anyhow::Result<Response> {
    let db_url = match variables::get("db_url") {
        Ok(url) if !url.is_empty() => url,
        _ => return Ok(Response::builder().status(500).body("Missing db_url").build())
    };

    let connection = match Connection::open(&db_url) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("Failed to connect to db for health check: {:?}", e);
            return Ok(Response::builder().status(500).body("Internal DB error").build());
        }
    };

    let query = "SELECT process_id, heartbeat::text, (heartbeat > NOW() - INTERVAL '90 seconds') as is_active FROM scheduler_election WHERE role = 'leader' LIMIT 1";
    let row_set = match connection.query(query, &[]) {
        Ok(rs) => rs,
        Err(e) => {
            eprintln!("Failed to query election table: {:?}", e);
            return Ok(Response::builder().status(500).body("Internal DB error").build());
        }
    };

    let mut is_leader_active = false;
    let mut leader_pid = "unknown".to_string();
    let mut last_seen = "unknown".to_string();

    if !row_set.rows.is_empty() {
        if let DbValue::Str(pid) = &row_set.rows[0][0] {
            leader_pid = pid.clone();
        }
        if let DbValue::Str(s) = &row_set.rows[0][1] {
            last_seen = s.clone();
        }
        if let DbValue::Boolean(active) = &row_set.rows[0][2] {
            is_leader_active = *active;
        }
    }

    #[derive(Serialize)]
    struct HealthResponse {
        status: String,
        home_server_active: bool,
        leader_pid: String,
        last_seen: String,
    }

    let resp = HealthResponse {
        status: "ok".to_string(),
        home_server_active: is_leader_active,
        leader_pid,
        last_seen,
    };

    Ok(Response::builder()
        .status(200)
        .header("content-type", "application/json")
        .body(serde_json::to_string(&resp).unwrap())
        .build())
}

#[derive(Deserialize)]
struct HeartbeatRequest {
    role: String,
    process_id: String,
}

#[derive(Serialize)]
struct HeartbeatResponse {
    status: String,
    mcp_server_active: bool,
}

async fn handle_heartbeat_post(req: Request) -> anyhow::Result<Response> {
    let body_bytes = req.into_body();
    let body_str = match std::str::from_utf8(&body_bytes) {
        Ok(s) => s,
        Err(_) => return Ok(Response::builder().status(400).body("Invalid UTF-8 body").build())
    };

    let req_data: HeartbeatRequest = match serde_json::from_str(body_str) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("JSON parse error: {}", e);
            return Ok(Response::builder().status(400).body("Invalid JSON payload").build())
        }
    };

    let db_url = match variables::get("db_url") {
        Ok(url) if !url.is_empty() => url,
        _ => return Ok(Response::builder().status(500).body("Missing db_url").build())
    };

    let connection = match Connection::open(&db_url) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("DB Connection failed: {:?}", e);
            return Ok(Response::builder().status(500).body("Internal DB Error").build())
        }
    };

    // Upsert the heartbeat
    let upsert_query = "
        INSERT INTO scheduler_election (role, process_id, heartbeat)
        VALUES ($1, $2, CURRENT_TIMESTAMP)
        ON CONFLICT (role) DO UPDATE SET
            process_id = EXCLUDED.process_id,
            heartbeat = CURRENT_TIMESTAMP
    ";
    
    let _ = connection.execute(
        upsert_query,
        &[
            ParameterValue::Str(req_data.role.clone()),
            ParameterValue::Str(req_data.process_id.clone())
        ]
    );

    // Query MCP Server status (fallback to checking 'leader' for backward compatibility)
    let query = "SELECT (heartbeat > NOW() - INTERVAL '90 seconds') as is_active FROM scheduler_election WHERE role IN ('leader', 'mcp_server') ORDER BY heartbeat DESC LIMIT 1";
    let row_set = match connection.query(query, &[]) {
        Ok(rs) => rs,
        Err(_) => return Ok(Response::builder().status(500).body("Internal DB Error").build())
    };

    let mut is_mcp_active = false;
    if !row_set.rows.is_empty() {
        if let DbValue::Boolean(active) = &row_set.rows[0][0] {
            is_mcp_active = *active;
        }
    }

    let resp = HeartbeatResponse {
        status: "ok".to_string(),
        mcp_server_active: is_mcp_active,
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
    let body_str = match std::str::from_utf8(&body_bytes) {
        Ok(s) => s,
        Err(_) => return Ok(Response::builder().status(400).body("Invalid UTF-8 body").build())
    };

    let req_data: MultiplierRequest = match serde_json::from_str(body_str) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("JSON parse error: {}", e);
            return Ok(Response::builder().status(400).body("Invalid JSON payload").build())
        }
    };

    let db_url = match variables::get("db_url") {
        Ok(url) if !url.is_empty() => url,
        _ => return Ok(Response::builder().status(500).body("Missing db_url").build())
    };

    let connection = match Connection::open(&db_url) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("DB Connection failed: {:?}", e);
            return Ok(Response::builder().status(500).body("Internal DB Error").build())
        }
    };

    let query = "UPDATE language_stats SET pump_multiplier = $1 WHERE user_id = $2 AND language_name = $3";
    match connection.execute(query, &[ParameterValue::Floating64(req_data.multiplier), ParameterValue::Str(user_id), ParameterValue::Str(req_data.name.to_uppercase())]) {
        Ok(_) => Ok(Response::builder().status(200).body("Multiplier updated").build()),
        Err(e) => {
            eprintln!("Update failed: {:?}", e);
            Ok(Response::builder().status(500).body("Database update failed").build())
        }
    }
}

async fn handle_languages_get(req: Request) -> anyhow::Result<Response> {
    let auth_header = req.header("authorization");
    let user_id = match extract_user_id(auth_header).await {
        Some(id) => id,
        None => return Ok(Response::builder().status(401).body("Unauthorized").build()),
    };

    let db_url = match variables::get("db_url") {
        Ok(url) if !url.is_empty() => url,
        _ => return Ok(Response::builder().status(500).body("Missing db_url").build())
    };

    let connection = Connection::open(&db_url)?;
    
    let query = "SELECT language_name, current_reviews, tomorrow_reviews, next_7_days_reviews, daily_rate, safebuf, derail_risk, pump_multiplier FROM language_stats WHERE user_id = $1";
    let row_set = match connection.query(query, &[ParameterValue::Str(user_id)]) {
        Ok(rs) => rs,
        Err(e) => {
            eprintln!("Database error: {:?}", e);
            return Ok(Response::builder().status(500).body("Internal Server Error").build());
        }
    };

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
    }

    #[derive(Serialize)]
    struct LanguagesResponse {
        languages: Vec<LanguageStat>,
    }

    let mut languages = Vec::new();
    for row in row_set.rows {
        let name = match &row[0] {
            DbValue::Str(s) => s.clone(),
            _ => continue,
        };
        let current = match &row[1] {
            DbValue::Int32(i) => *i,
            _ => 0,
        };
        let tomorrow = match &row[2] {
            DbValue::Int32(i) => *i,
            _ => 0,
        };
        let next_7_days = match &row[3] {
            DbValue::Int32(i) => *i,
            _ => 0,
        };
        let daily_rate = match &row[4] {
            DbValue::Floating64(f) => *f,
            DbValue::Floating32(f) => *f as f64,
            _ => 0.0,
        };
        let safebuf = match &row[5] {
            DbValue::Int32(i) => *i,
            _ => 0,
        };
        let derail_risk = match &row[6] {
            DbValue::Str(s) => s.clone(),
            _ => "SAFE".to_string(),
        };
        let pump_multiplier = match &row[7] {
            DbValue::Floating64(f) => *f,
            DbValue::Floating32(f) => *f as f64,
            DbValue::Int32(i) => *i as f64,
            _ => 1.0,
        };
        languages.push(LanguageStat {
            name,
            current,
            tomorrow,
            next_7_days,
            daily_rate,
            safebuf,
            derail_risk,
            pump_multiplier,
        });
    }

    let resp = LanguagesResponse { languages };

    Ok(Response::builder()
        .status(200)
        .header("content-type", "application/json")
        .body(serde_json::to_string(&resp).unwrap())
        .build())
}

async fn handle_budget_get(req: Request) -> anyhow::Result<Response> {
    let auth_header = req.header("authorization");
    let user_id = match extract_user_id(auth_header).await {
        Some(id) => id,
        None => return Ok(Response::builder().status(401).body("Unauthorized").build()),
    };

    let db_url = match variables::get("db_url") {
        Ok(url) if !url.is_empty() => url,
        _ => return Ok(Response::builder().status(500).body("Missing db_url").build())
    };

    let connection = Connection::open(&db_url)?;
    
    let query = "SELECT remaining_budget FROM budget_tracking WHERE user_id = $1 LIMIT 1";
    let row_set = match connection.query(query, &[ParameterValue::Str(user_id)]) {
        Ok(rs) => rs,
        Err(e) => {
            eprintln!("Database error: {:?}", e);
            return Ok(Response::builder().status(500).body("Internal Server Error").build());
        }
    };
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

    Ok(Response::builder()
        .status(200)
        .header("content-type", "application/json")
        .body(serde_json::to_string(&resp).unwrap())
        .build())
}

async fn handle_walks_post(req: Request) -> anyhow::Result<Response> {

    let auth_header = req.header("authorization");
    let user_id = match extract_user_id(auth_header).await {
        Some(id) => id,
        None => {
            if let Ok(bypass) = variables::get("auth_bypass") {
                if bypass == "true" {
                    "dev_user_123".to_string()
                } else {
                    return Ok(Response::builder()
                        .status(401)
                        .body("Unauthorized: Missing or invalid JWT")
                        .build());
                }
            } else {
                return Ok(Response::builder()
                    .status(401)
                    .body("Unauthorized: Missing or invalid JWT")
                    .build());
            }
        }
    };

    let body_bytes = req.body();
    let walk: WalkDataSummary = match serde_json::from_slice(body_bytes) {
        Ok(w) => w,
        Err(e) => {
            return Ok(Response::builder()
                .status(400)
                .body(format!("Invalid JSON: {}", e))
                .build())
        }
    };

    let db_url = match variables::get("db_url") {
        Ok(url) if !url.is_empty() => url,
        _ => {
            println!("Parsed walk payload for user {}: {:?}", user_id, walk);
            let resp = StatusResponse {
                status: "success".to_string(),
                message: "Walk ingested (DB skipped)".to_string(),
            };
            return Ok(Response::builder()
                .status(201)
                .header("content-type", "application/json")
                .body(serde_json::to_string(&resp).unwrap())
                .build());
        }
    };

    let connection = Connection::open(&db_url)?;

    // 1. Ensure the user exists (Upsert)
    let user_upsert_query = r#"
        INSERT INTO users (pocket_id_sub, beeminder_token_encrypted, beeminder_goal)
        VALUES ($1, '', 'bike')
        ON CONFLICT (pocket_id_sub) DO NOTHING
    "#;
    let user_params = vec![ParameterValue::Str(user_id.clone())];
    let _ = connection.execute(user_upsert_query, &user_params);

    // 2. Check Cooldown/Update availability
    let existing_query = r#"
        SELECT id, step_count FROM walk_inferences 
        WHERE user_id = $1 
        AND start_time = $2
        LIMIT 1
    "#;
    let existing_params = vec![ParameterValue::Str(user_id.clone()), ParameterValue::Str(walk.start_time.clone())];
    let existing_rs = connection.query(existing_query, &existing_params)?;
    
    if !existing_rs.rows.is_empty() {
        let existing_steps_str = match &existing_rs.rows[0][1] {
            DbValue::Str(s) => s.clone(),
            _ => "0".to_string(),
        };
        let existing_steps: i32 = existing_steps_str.parse().unwrap_or(0);
        
        // Only allow update if steps increased by more than 50
        if walk.step_count <= existing_steps + 50 {
            println!("Sync suppressed for user {}: data stagnant ({} -> {})", user_id, existing_steps, walk.step_count);
            let resp = StatusResponse {
                status: "success".to_string(),
                message: "Walk ingested (Duplicate suppressed via cooldown)".to_string(),
            };
            return Ok(Response::builder()
                .status(200)
                .header("content-type", "application/json")
                .body(serde_json::to_string(&resp).unwrap())
                .build());
        }
        println!("Updating existing walk for user {}: ({} -> {})", user_id, existing_steps, walk.step_count);
    }

    // 3. Upsert walk record
    let query = r#"
        INSERT INTO walk_inferences (
            user_id, start_time, end_time, step_count, distance_meters, distance_source, confidence_score, gps_route_points, status
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'logging')
        ON CONFLICT (user_id, start_time) DO UPDATE SET 
            end_time = EXCLUDED.end_time,
            step_count = EXCLUDED.step_count,
            distance_meters = EXCLUDED.distance_meters,
            status = 'logging'
    "#;

    let params = vec![
        ParameterValue::Str(user_id.clone()),
        ParameterValue::Str(walk.start_time.clone()),
        ParameterValue::Str(walk.end_time.clone()),
        ParameterValue::Str(walk.step_count.to_string()),
        ParameterValue::Str(walk.distance_meters.to_string()),
        ParameterValue::Str(walk.distance_source.clone()),
        ParameterValue::Str(walk.confidence_score.to_string()),
        ParameterValue::Str(walk.gps_route_points.to_string()),
    ];

    if let Err(e) = connection.execute(query, &params) {
        eprintln!("Database error: {:?}", e);
        return Ok(Response::builder().status(500).body("Internal Server Error").build());
    }

    // 4. Fetch Beeminder config
    let token_query = "SELECT beeminder_token_encrypted, beeminder_goal, beeminder_user FROM users WHERE pocket_id_sub = $1 LIMIT 1";
    let token_params = vec![ParameterValue::Str(user_id.clone())];
    let row_set = connection.query(token_query, &token_params)?;

    if row_set.rows.is_empty() {
        let resp = StatusResponse { status: "success".to_string(), message: "Walk saved. (No Beeminder token found)".to_string() };
        return Ok(Response::builder().status(201).header("content-type", "application/json").body(serde_json::to_string(&resp).unwrap()).build());
    }

    let beeminder_token_raw = match &row_set.rows[0][0] { DbValue::Str(s) => s.clone(), _ => return Ok(Response::builder().status(500).body("Invalid token").build()) };
    let beeminder_token = match decrypt_token(&beeminder_token_raw).await {
        Ok(t) => t,
        Err(_) => {
            // Fallback to plaintext for migration period
            println!("Warning: Using plaintext Beeminder token for user {}", user_id);
            beeminder_token_raw
        }
    };
    let beeminder_goal = match &row_set.rows[0][1] { DbValue::Str(s) if !s.is_empty() => s.clone(), _ => "bike".to_string() };
    let beeminder_user = match &row_set.rows[0][2] { DbValue::Str(s) if !s.is_empty() => s.clone(), _ => "me".to_string() };

    // 5. Beeminder API Call with correct requestid (no underscore) in URL
    let miles = walk.distance_meters / 1609.34;
    let request_id = format!("{}_{}", user_id, walk.start_time);
    let beeminder_url = format!("https://www.beeminder.com/api/v1/users/{}/goals/{}/datapoints.json?requestid={}", beeminder_user, beeminder_goal, request_id);
    let beeminder_body = format!(
        "auth_token={}&value={:.2}&comment=Logged via Mecris-Go Spin Backend (Steps: {}, Source: {})",
        beeminder_token, miles, walk.step_count, walk.distance_source
    );

    let beeminder_req = Request::post(&beeminder_url, beeminder_body)
        .header("content-type", "application/x-www-form-urlencoded")
        .build();

    let beeminder_res: Response = spin_sdk::http::send(beeminder_req).await?;
    let status = *beeminder_res.status();
    
    if (200..=299).contains(&status) {
        // Success: Mark as logged
        let update_query = "UPDATE walk_inferences SET status = 'logged' WHERE user_id = $1 AND start_time = $2";
        let update_params = vec![ParameterValue::Str(user_id.clone()), ParameterValue::Str(walk.start_time.clone())];
        let _ = connection.execute(update_query, &update_params);
        
        let resp = StatusResponse { status: "success".to_string(), message: format!("Walk synced: {:.2} miles", miles) };
        Ok(Response::builder().status(201).header("content-type", "application/json").body(serde_json::to_string(&resp).unwrap()).build())
    } else {
        // Failure: Rollback to pending
        let rollback_query = "UPDATE walk_inferences SET status = 'pending' WHERE user_id = $1 AND start_time = $2";
        let rollback_params = vec![ParameterValue::Str(user_id.clone()), ParameterValue::Str(walk.start_time.clone())];
        let _ = connection.execute(rollback_query, &rollback_params);
        
        let resp = StatusResponse { status: "partial_success".to_string(), message: "Saved locally, Beeminder sync failed.".to_string() };
        Ok(Response::builder().status(201).header("content-type", "application/json").body(serde_json::to_string(&resp).unwrap()).build())
    }
}
