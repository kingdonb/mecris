use serde::{Deserialize, Serialize};
use spin_sdk::{
    http::{IntoResponse, Request, Response},
    http_component,
    pg::{Connection, ParameterValue},
    variables,
};

#[derive(Deserialize, Debug)]
struct WalkDataSummary {
    start_time: String,
    end_time: String,
    step_count: i32,
    distance_meters: f64,
    distance_source: String,
    confidence_score: f64,
    gps_route_points: i32,
    timezone: String,
}

#[derive(Serialize)]
struct StatusResponse {
    status: String,
    message: String,
}

#[http_component]
fn handle_sync_service(req: Request) -> anyhow::Result<impl IntoResponse> {
    if req.method() != &spin_sdk::http::Method::Post {
        return Ok(Response::builder()
            .status(405)
            .body("Method Not Allowed")
            .build());
    }

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

    // Hardcoded user_id for Phase 2.1 before Pocket ID integration
    let user_id = "dev_user_123";

    // Write to Neon DB
    let db_url = match variables::get("db_url") {
        Ok(url) if !url.is_empty() => url,
        _ => {
            println!("Parsed walk payload (No DB configured): {:?}", walk);
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
        ParameterValue::Str(user_id.to_string()),
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
                message: "Walk ingested and saved to DB".to_string(),
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
