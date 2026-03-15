use serde::{Deserialize, Serialize};
use spin_sdk::{
    http::{IntoResponse, Request, Response},
    http_component,
    pg::{Connection, ParameterValue},
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
    confidence_score: f64,
    gps_route_points: i32,
    #[allow(dead_code)]
    timezone: String,
}

#[derive(Serialize)]
struct StatusResponse {
    status: String,
    message: String,
}

// Minimal JWT structure for decoding (without full signature validation for this immediate iteration)
#[derive(Deserialize, Debug)]
struct JwtClaims {
    sub: String,
    // Pocket ID might include other claims, but we only strictly need 'sub' (User ID) for now
    #[allow(dead_code)]
    exp: Option<usize>,
}

fn extract_user_id(auth_header: Option<&spin_sdk::http::HeaderValue>) -> Option<String> {
    let header_val = std::str::from_utf8(auth_header?.as_ref()).ok()?;
    if !header_val.starts_with("Bearer ") {
        return None;
    }
    let token = &header_val[7..];

    // Split JWT: header.payload.signature
    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() != 3 {
        return None;
    }

    // Decode payload
    let payload_bytes = URL_SAFE_NO_PAD.decode(parts[1]).ok()?;
    let claims: JwtClaims = serde_json::from_slice(&payload_bytes).ok()?;

    Some(claims.sub)
}

#[http_component]
fn handle_sync_service(req: Request) -> anyhow::Result<impl IntoResponse> {
    if req.method() != &spin_sdk::http::Method::Post {
        return Ok(Response::builder()
            .status(405)
            .body("Method Not Allowed")
            .build());
    }

    // P2-2: Pocket ID Integration - JWT Check
    let auth_header = req.header("authorization");
    let user_id = match extract_user_id(auth_header) {
        Some(id) => id,
        None => {
            // For testing, if a specific dev variable is set, we can allow bypass, otherwise strictly block
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

    // Write to Neon DB
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

    let query = r#"
        INSERT INTO walk_inferences (
            user_id, start_time, end_time, step_count, distance_meters, distance_source, confidence_score, gps_route_points
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    "#;

    let params = vec![
        ParameterValue::Str(user_id.clone()),
        ParameterValue::Str(walk.start_time),
        ParameterValue::Str(walk.end_time),
        ParameterValue::Int32(walk.step_count),
        ParameterValue::Floating64(walk.distance_meters),
        ParameterValue::Str(walk.distance_source),
        ParameterValue::Floating64(walk.confidence_score),
        ParameterValue::Int32(walk.gps_route_points),
    ];

    match connection.execute(query, &params) {
        Ok(_) => {
            let resp = StatusResponse {
                status: "success".to_string(),
                message: format!("Walk ingested and saved to DB for user {}", user_id),
            };
            Ok(Response::builder()
                .status(201)
                .header("content-type", "application/json")
                .body(serde_json::to_string(&resp).unwrap())
                .build())
        }
        Err(e) => {
            eprintln!("Database error: {:?}", e);
            Ok(Response::builder()
                .status(500)
                .body("Internal Server Error")
                .build())
        }
    }
}
