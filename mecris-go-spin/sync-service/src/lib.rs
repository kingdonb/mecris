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
    let db_url = match variables::get("db_url") {
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

#[derive(Deserialize, Debug, Serialize)]
struct JwtClaims {
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

async fn extract_user_id(auth_header: Option<&spin_sdk::http::HeaderValue>) -> Option<String> {
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
        return handle_health_get(req).await;
    } else if path == "/heartbeat" {
        if req.method() != &spin_sdk::http::Method::Post {
            return Ok(Response::builder().status(405).body("Method Not Allowed").build());
        }
        return handle_heartbeat_post(req).await;
    } else if path == "/internal/failover-sync" {
        return handle_failover_sync(req).await;
    }
    
    Ok(Response::builder().status(404).body("Not Found").build())
}

async fn handle_failover_sync(req: Request) -> anyhow::Result<Response> {
    let auth_header = req.header("authorization");
    let user_id = match extract_user_id(auth_header).await {
        Some(id) => id,
        None => return Ok(Response::builder().status(401).body("Unauthorized").build()),
    };

    let db_url = variables::get("db_url").map_err(|e| anyhow::anyhow!("db_url fetch failed: {:?}", e))?;
    let connection = Connection::open(&db_url).map_err(|e| anyhow::anyhow!("DB connection failed: {:?}", e))?;

    let _ = connection.execute(
        "INSERT INTO users (pocket_id_sub, beeminder_token_encrypted, beeminder_goal) VALUES ($1, '', 'bike') ON CONFLICT DO NOTHING",
        &[ParameterValue::Str(user_id.clone())]
    );

    match run_clozemaster_scraper(&db_url, &user_id).await {
        Ok(_) => {
            let resp = StatusResponse { status: "success".to_string(), message: "Failover sync complete".to_string() };
            Ok(Response::builder().status(200).header("content-type", "application/json").body(serde_json::to_string(&resp).unwrap()).build())
        }
        Err(e) => {
            let error_msg = format!("Failover sync failed: {}", e);
            eprintln!("{}", error_msg);
            let resp = StatusResponse { status: "error".to_string(), message: error_msg };
            Ok(Response::builder().status(500).header("content-type", "application/json").body(serde_json::to_string(&resp).unwrap()).build())
        }
    }
}

async fn run_clozemaster_scraper(db_url: &str, user_id: &str) -> anyhow::Result<()> {
    let email = variables::get("clozemaster_email")?;
    let password = variables::get("clozemaster_password")?;
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
    
    let status = *res.status();
    if !(200..400).contains(&status) {
        return Err(anyhow::anyhow!("Clozemaster login failed with status {}", status));
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
    
    let status = *res.status();
    // Allow 302 if it's redirecting to the dashboard itself
    if !(200..300).contains(&status) && status != 302 {
        return Err(anyhow::anyhow!("Clozemaster dashboard fetch failed with status {}", status));
    }

    let mut body_str = std::str::from_utf8(res.body()).unwrap_or("").to_string();

    // If it's a redirect, we might need to follow it once to get the final page
    if status == 302 {
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
    
    let props_json = html_escape::decode_html_entities(props_escaped);
    let props: serde_json::Value = serde_json::from_str(&props_json)?;
    
    let connection = Connection::open(db_url)?;
    
    if let Some(pairings) = props.get("languagePairings").and_then(|l| l.as_array()) {
        for pair in pairings {
            let name = pair.get("slug").and_then(|n| n.as_str()).unwrap_or("UNKNOWN");
            let current = pair.get("numReadyForReview").and_then(|c| c.as_i64()).unwrap_or(0) as i32;
            
            // Map slugs to standard names if possible
            let lang_name = match name {
                "ara-eng" => "ARABIC",
                "ell-eng" => "GREEK",
                _ => name,
            };

            let query = "INSERT INTO language_stats (user_id, language_name, current_reviews, last_updated) 
                         VALUES ($1, $2, $3, CURRENT_TIMESTAMP) 
                         ON CONFLICT (user_id, language_name) DO UPDATE SET 
                         current_reviews = EXCLUDED.current_reviews, 
                         last_updated = CURRENT_TIMESTAMP";
            let _ = connection.execute(query, &[
                ParameterValue::Str(user_id.to_string()),
                ParameterValue::Str(lang_name.to_uppercase()), 
                ParameterValue::Int32(current)
            ]);
        }
    }
    Ok(())
}

async fn handle_health_get(req: Request) -> anyhow::Result<Response> {
    let auth_header = req.header("authorization");
    let user_id = match extract_user_id(auth_header).await {
        Some(id) => id,
        None => return Ok(Response::builder().status(401).body("Unauthorized").build()),
    };

    let db_url = variables::get("db_url")?;
    let connection = Connection::open(&db_url)?;
    
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

    let db_url = variables::get("db_url")?;
    let connection = Connection::open(&db_url)?;
    
    // Atomic leadership claim with user scoping
    let update_query = "
        INSERT INTO scheduler_election (user_id, role, process_id, heartbeat) 
        VALUES ($1, 'leader', $2, CURRENT_TIMESTAMP) 
        ON CONFLICT (user_id, role) DO UPDATE SET 
            process_id = EXCLUDED.process_id, 
            heartbeat = CURRENT_TIMESTAMP 
        WHERE scheduler_election.process_id = $2 
           OR scheduler_election.heartbeat < CURRENT_TIMESTAMP - INTERVAL '90 seconds'
           OR scheduler_election.process_id IS NULL";
    
    let result = connection.execute(update_query, &[ParameterValue::Str(user_id), ParameterValue::Str(pid.to_string())])?;
    
    let claimed = result > 0;

    #[derive(Serialize)]
    struct HeartbeatResponse {
        status: String,
        is_leader: bool,
    }
    let resp = HeartbeatResponse { 
        status: "ok".to_string(), 
        is_leader: claimed 
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

    let db_url = variables::get("db_url")?;
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

    let db_url = variables::get("db_url")?;
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
        let slug = match &row[8] { DbValue::Str(s) => Some(s.clone()), _ => None };
        LanguageStat {
            name: match &row[0] { DbValue::Str(s) => s.clone(), _ => "".to_string() },
            current: match &row[1] { DbValue::Int32(i) => *i, _ => 0 },
            tomorrow: match &row[2] { DbValue::Int32(i) => *i, _ => 0 },
            next_7_days: match &row[3] { DbValue::Int32(i) => *i, _ => 0 },
            daily_rate: match &row[4] { DbValue::Floating64(f) => *f, _ => 0.0 },
            safebuf: match &row[5] { DbValue::Int32(i) => *i, _ => 0 },
            derail_risk: match &row[6] { DbValue::Str(s) => s.clone(), _ => "SAFE".to_string() },
            pump_multiplier: match &row[7] { DbValue::Floating64(f) => *f, _ => 1.0 },
            has_goal: slug.as_ref().map_or(false, |s| !s.is_empty()),
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

    let db_url = variables::get("db_url")?;
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

    let db_url = variables::get("db_url")?;
    let connection = Connection::open(&db_url)?;

    let _ = connection.execute(
        "INSERT INTO users (pocket_id_sub, beeminder_token_encrypted, beeminder_goal) VALUES ($1, '', 'bike') ON CONFLICT DO NOTHING",
        &[ParameterValue::Str(user_id.clone())]
    );

    let query = r#"
        INSERT INTO walk_inferences (user_id, start_time, end_time, step_count, distance_meters, distance_source, confidence_score, gps_route_points, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'logging')
        ON CONFLICT (user_id, start_time) DO UPDATE SET end_time = EXCLUDED.end_time, step_count = EXCLUDED.step_count, status = 'logging'
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

    // Restore Beeminder Sync
    let token_rs = connection.query(
        "SELECT beeminder_token_encrypted, beeminder_goal, beeminder_user FROM users WHERE pocket_id_sub = $1",
        &[ParameterValue::Str(user_id.clone())]
    )?;

    if !token_rs.rows.is_empty() {
        let token_raw = match &token_rs.rows[0][0] { DbValue::Str(s) => s.clone(), _ => "".to_string() };
        let token = decrypt_token(&token_raw).await.unwrap_or(token_raw);
        let goal = match &token_rs.rows[0][1] { DbValue::Str(s) => s.clone(), _ => "bike".to_string() };
        let user = match &token_rs.rows[0][2] { DbValue::Str(s) => s.clone(), _ => "me".to_string() };

        let miles = walk.distance_meters / 1609.34;
        let beeminder_url = format!("https://www.beeminder.com/api/v1/users/{}/goals/{}/datapoints.json", user, goal);
        let beeminder_body = format!("auth_token={}&value={:.2}&comment=Synced via Spin", token, miles);

        let beeminder_req = Request::post(&beeminder_url, beeminder_body).header("content-type", "application/x-www-form-urlencoded").build();
        let _: Response = spin_sdk::http::send(beeminder_req).await?;
    }

    let resp = StatusResponse { status: "success".to_string(), message: "Walk ingested".to_string() };
    Ok(Response::builder().status(201).header("content-type", "application/json").body(serde_json::to_string(&resp).unwrap()).build())
}
