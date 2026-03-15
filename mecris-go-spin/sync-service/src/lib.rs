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
    if req.method() != &spin_sdk::http::Method::Post {
        return Ok(Response::builder()
            .status(405)
            .body("Method Not Allowed")
            .build());
    }

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
    if let Err(e) = connection.execute(user_upsert_query, &user_params) {
        eprintln!("User upsert error: {:?}", e);
        // We continue anyway, the walk insert will fail if this was a hard error
    }

    // 2. Write the telemetry to Neon DB
    let query = r#"
        INSERT INTO walk_inferences (
            user_id, start_time, end_time, step_count, distance_meters, distance_source, confidence_score, gps_route_points
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (user_id, start_time) DO NOTHING
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

    let res = connection.execute(query, &params);
    println!("Database write result: {:?}", res);
    
    if let Err(e) = res {
        eprintln!("Database error: {:?}", e);
        return Ok(Response::builder()
            .status(500)
            .body("Internal Server Error")
            .build());
    } else {
        println!("Successfully inserted/updated walk for user {}", user_id);
    }

    // 3. Fetch the Beeminder Token, Goal, and User
    let token_query = "SELECT beeminder_token_encrypted, beeminder_goal, beeminder_user FROM users WHERE pocket_id_sub = $1 LIMIT 1";
    let token_params = vec![ParameterValue::Str(user_id.clone())];
    let row_set = match connection.query(token_query, &token_params) {
        Ok(rs) => rs,
        Err(e) => {
            eprintln!("Error fetching token: {:?}", e);
            return Ok(Response::builder()
                .status(500)
                .body("Internal Server Error")
                .build());
        }
    };

    if row_set.rows.is_empty() {
        // We logged the walk, but the user hasn't set up Beeminder integration yet.
        let resp = StatusResponse {
            status: "success".to_string(),
            message: "Walk saved. (No Beeminder token found)".to_string(),
        };
        return Ok(Response::builder()
            .status(201)
            .header("content-type", "application/json")
            .body(serde_json::to_string(&resp).unwrap())
            .build());
    }

    // 3. Fetch the Beeminder Token, Goal, and User
    let token_query = "SELECT beeminder_token_encrypted, beeminder_goal, beeminder_user FROM users WHERE pocket_id_sub = $1 LIMIT 1";
    let token_params = vec![ParameterValue::Str(user_id.clone())];
    let row_set = match connection.query(token_query, &token_params) {
        Ok(rs) => rs,
        Err(e) => {
            eprintln!("Error fetching token: {:?}", e);
            return Ok(Response::builder()
                .status(500)
                .body("Internal Server Error")
                .build());
        }
    };

    if row_set.rows.is_empty() {
        let resp = StatusResponse {
            status: "success".to_string(),
            message: "Walk saved. (No Beeminder token found)".to_string(),
        };
        return Ok(Response::builder()
            .status(201)
            .header("content-type", "application/json")
            .body(serde_json::to_string(&resp).unwrap())
            .build());
    }

    // --- IDEMPOTENCY CHECK (Server Side) ---
    // Check if we've already synced a walk for this user in the last 4 hours
    let cooldown_query = r#"
        SELECT id FROM walk_inferences 
        WHERE user_id = $1 
        AND status = 'logged' 
        AND created_at > NOW() - INTERVAL '4 hours'
        LIMIT 1
    "#;
    let cooldown_params = vec![ParameterValue::Str(user_id.clone())];
    let cooldown_rs = connection.query(cooldown_query, &cooldown_params)?;
    
    if !cooldown_rs.rows.is_empty() {
        println!("Sync suppressed for user {}: cooldown active (4h)", user_id);
        let resp = StatusResponse {
            status: "success".to_string(),
            message: "Walk ingested (Duplicate suppressed via cooldown)".to_string(),
        };
        return Ok(Response::builder()
            .status(200) // Return 200 OK so phone stops retrying
            .header("content-type", "application/json")
            .body(serde_json::to_string(&resp).unwrap())
            .build());
    }
    // --- END IDEMPOTENCY CHECK ---

    let beeminder_token = match &row_set.rows[0][0] {
        DbValue::Str(s) => s.clone(),
        _ => return Ok(Response::builder()
            .status(500)
            .body("Invalid token format in DB")
            .build()),
    };

    let beeminder_goal = match &row_set.rows[0][1] {
        DbValue::Str(s) if !s.is_empty() => s.clone(),
        _ => "bike".to_string(), // Fallback to bike if not set
    };

    let beeminder_user = match &row_set.rows[0][2] {
        DbValue::Str(s) if !s.is_empty() => s.clone(),
        _ => "me".to_string(), // Fallback to 'me' if not set
    };

    // 4. Dispatch to Beeminder API
    // Calculate miles from meters (1 mile = 1609.34 meters)
    let miles = walk.distance_meters / 1609.34;
    
    // We use the start_time + user_id as an idempotency key (request_id)
    let request_id = format!("{}_{}", user_id, walk.start_time);
    let beeminder_url = format!(
        "https://www.beeminder.com/api/v1/users/{}/goals/{}/datapoints.json?auth_token={}",
        beeminder_user, beeminder_goal, beeminder_token
    );
    let beeminder_body = format!(
        "value={:.2}&comment=Logged via Mecris-Go Spin Backend (Steps: {}, Source: {})&request_id={}",
        miles, walk.step_count, walk.distance_source, request_id
    );

    let beeminder_req = Request::post(&beeminder_url, beeminder_body)
        .header("content-type", "application/x-www-form-urlencoded")
        .build();

    let beeminder_res: Response = spin_sdk::http::send(beeminder_req).await?;
    let status = *beeminder_res.status();
    
    if (200..=299).contains(&status) {
        // Mark walk as logged to trigger cooldown
        let update_query = "UPDATE walk_inferences SET status = 'logged' WHERE user_id = $1 AND start_time = $2";
        let update_params = vec![
            ParameterValue::Str(user_id.clone()),
            ParameterValue::Str(walk.start_time.clone()),
        ];
        let _ = connection.execute(update_query, &update_params);
    } else {
        eprintln!("Failed to log to Beeminder: {:?}", beeminder_res.status());
        let resp = StatusResponse {
            status: "partial_success".to_string(),
            message: "Walk saved locally, but failed to sync to Beeminder.".to_string(),
        };
        return Ok(Response::builder()
            .status(201)
            .header("content-type", "application/json")
            .body(serde_json::to_string(&resp).unwrap())
            .build());
    }

    let resp = StatusResponse {
        status: "success".to_string(),
        message: format!("Walk ingested and synced to Beeminder for user {}", user_id),
    };
    Ok(Response::builder()
        .status(201)
        .header("content-type", "application/json")
        .body(serde_json::to_string(&resp).unwrap())
        .build())
}
