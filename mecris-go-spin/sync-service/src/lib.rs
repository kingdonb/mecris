use serde::{Deserialize, Serialize};
use spin_sdk::{
    http::{IntoResponse, Request, Response},
    http_component,
    pg::{Connection, ParameterValue, DbValue},
    variables,
};
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};

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

#[derive(Deserialize, Debug)]
struct JwtClaims {
    sub: String,
    #[allow(dead_code)]
    exp: Option<usize>,
}

fn extract_user_id(auth_header: Option<&spin_sdk::http::HeaderValue>) -> Option<String> {
    let header_val = std::str::from_utf8(auth_header?.as_ref()).ok()?;
    if !header_val.starts_with("Bearer ") {
        return None;
    }
    let token = &header_val[7..];

    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() != 3 {
        return None;
    }

    let payload_bytes = URL_SAFE_NO_PAD.decode(parts[1]).ok()?;
    let claims: JwtClaims = serde_json::from_slice(&payload_bytes).ok()?;

    Some(claims.sub)
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
    }
    
    Ok(Response::builder().status(404).body("Not Found").build())
}

async fn handle_languages_get(_req: Request) -> anyhow::Result<Response> {
    let db_url = match variables::get("db_url") {
        Ok(url) if !url.is_empty() => url,
        _ => return Ok(Response::builder().status(500).body("Missing db_url").build())
    };

    let connection = Connection::open(&db_url)?;
    
    let query = "SELECT language_name, current_reviews, tomorrow_reviews, next_7_days_reviews FROM language_stats";
    let row_set = match connection.query(query, &[]) {
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
        languages.push(LanguageStat {
            name,
            current,
            tomorrow,
            next_7_days,
        });
    }

    let resp = LanguagesResponse { languages };

    Ok(Response::builder()
        .status(200)
        .header("content-type", "application/json")
        .body(serde_json::to_string(&resp).unwrap())
        .build())
}

async fn handle_budget_get(_req: Request) -> anyhow::Result<Response> {
    let db_url = match variables::get("db_url") {
        Ok(url) if !url.is_empty() => url,
        _ => return Ok(Response::builder().status(500).body("Missing db_url").build())
    };

    let connection = Connection::open(&db_url)?;
    
    let query = "SELECT remaining_budget FROM budget_tracking WHERE id = 1 LIMIT 1";
    let row_set = match connection.query(query, &[]) {
        Ok(rs) => rs,
        Err(e) => {
            eprintln!("Database error: {:?}", e);
            return Ok(Response::builder().status(500).body("Internal Server Error").build());
        }
    };

    if row_set.rows.is_empty() {
        return Ok(Response::builder().status(404).body("Budget not found").build());
    }

    let remaining_budget = match &row_set.rows[0][0] {
        DbValue::Floating64(f) => *f,
        DbValue::Floating32(f) => *f as f64,
        _ => return Ok(Response::builder().status(500).body("Invalid budget data type").build())
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
    let user_id = match extract_user_id(auth_header) {
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

    let beeminder_token = match &row_set.rows[0][0] { DbValue::Str(s) => s.clone(), _ => return Ok(Response::builder().status(500).body("Invalid token").build()) };
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
