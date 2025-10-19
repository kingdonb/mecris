use spin_sdk::http::{IntoResponse, Request, Response};
use spin_sdk::variables;
use serde_json::json;
use anyhow::Result;

mod sms;
mod time;

/// Main HTTP handler for walk reminder checks
#[spin_sdk::http_component]
fn handle_walk_check(_req: Request) -> Result<impl IntoResponse> {
    let result = check_and_send_reminder();
    
    match result {
        Ok(reminded) => {
            let response = json!({
                "status": "success",
                "reminded": reminded,
                "timestamp": chrono::Utc::now().to_rfc3339(),
                "dogs": ["Boris", "Fiona"]
            });
            
            Ok(Response::builder()
                .status(200)
                .header("content-type", "application/json")
                .body(response.to_string())
                .build())
        }
        Err(e) => {
            eprintln!("Walk reminder error: {}", e);
            let error_response = json!({
                "status": "error", 
                "error": e.to_string(),
                "timestamp": chrono::Utc::now().to_rfc3339()
            });
            
            Ok(Response::builder()
                .status(500)
                .header("content-type", "application/json")
                .body(error_response.to_string())
                .build())
        }
    }
}

/// Core logic: check if we should send a reminder and do it
fn check_and_send_reminder() -> Result<bool> {
    let current_hour = time::get_current_hour_eastern()?;
    
    // Only remind between 2 PM and 6 PM Eastern
    if !(14..=18).contains(&current_hour) {
        return Ok(false);
    }
    
    // Check if we already reminded today
    if already_reminded_today()? {
        return Ok(false);
    }
    
    // Send the reminder!
    let message = get_walk_message(current_hour);
    sms::send_walk_reminder(&message)?;
    
    // Mark that we sent a reminder today
    mark_reminder_sent()?;
    
    Ok(true)
}

/// Generate walk message based on time of day
fn get_walk_message(hour: u8) -> String {
    match hour {
        14..=15 => "🐕 Afternoon walk time! Boris and Fiona are ready for their adventure.".to_string(),
        16..=17 => "🌅 Golden hour walk! Boris and Fiona would love a sunset stroll.".to_string(),
        18..=19 => "🌆 Evening walk time! Boris and Fiona are waiting by the door.".to_string(),
        _ => "🐕 Walk time! Boris and Fiona need their daily adventure.".to_string(),
    }
}

/// Check if we already sent a reminder today (simple date-based check)
fn already_reminded_today() -> Result<bool> {
    let today = chrono::Utc::now().format("%Y-%m-%d").to_string();
    let key = format!("last_reminder_date");
    
    match spin_sdk::key_value::Store::open_default()?.get(&key) {
        Ok(Some(last_date)) => {
            let last_date_str = String::from_utf8_lossy(&last_date);
            Ok(last_date_str == today)
        }
        Ok(None) => Ok(false),
        Err(_) => Ok(false), // Assume not reminded if we can't check
    }
}

/// Mark that we sent a reminder today
fn mark_reminder_sent() -> Result<()> {
    let today = chrono::Utc::now().format("%Y-%m-%d").to_string();
    let key = format!("last_reminder_date");
    
    let store = spin_sdk::key_value::Store::open_default()?;
    store.set(&key, today.as_bytes())?;
    
    Ok(())
}