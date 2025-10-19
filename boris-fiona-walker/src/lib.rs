use spin_sdk::http::{IntoResponse, Request, Response};
use serde_json::json;
use anyhow::Result;

mod sms;
mod time;

/// Main HTTP handler for walk reminder checks
#[spin_sdk::http_component]
async fn handle_walk_check(req: Request) -> Result<Response> {
    let path = req.path();
    
    match path {
        "/check" => handle_check_api().await,
        "/" | "/debug" => handle_debug_frontend().await,
        _ => handle_debug_frontend().await, // Default to debug page
    }
}

/// Handle the API endpoint for walk reminder checks
async fn handle_check_api() -> Result<Response> {
    let result = check_and_send_reminder().await;
    
    match result {
        Ok(reminded) => {
            let response = json!({
                "status": "success",
                "reminded": reminded,
                "timestamp": chrono::Utc::now().to_rfc3339(),
                "dogs": ["Boris", "Fiona"],
                "spin_watch": "working! 🎉"
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

/// Handle the web frontend for debugging
async fn handle_debug_frontend() -> Result<Response> {
    let current_hour = time::get_current_hour_eastern().unwrap_or(0);
    let is_walk_time = (14..=18).contains(&current_hour);
    let already_reminded = already_reminded_today().unwrap_or(false);
    
    let html = format!(r#"
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🐕 Boris & Fiona Walk Reminder Debug</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
        }}
        .container {{
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 30px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(31, 38, 135, 0.37);
        }}
        h1 {{
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
        }}
        .status-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .status-card {{
            background: rgba(255,255,255,0.2);
            border-radius: 10px;
            padding: 20px;
            text-align: center;
        }}
        .status-value {{
            font-size: 2em;
            font-weight: bold;
            margin: 10px 0;
        }}
        .status-good {{ color: #4ade80; }}
        .status-warning {{ color: #fbbf24; }}
        .status-error {{ color: #f87171; }}
        .api-test {{
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 20px;
            margin-top: 20px;
        }}
        button {{
            background: #3b82f6;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1.1em;
            margin: 10px;
        }}
        button:hover {{
            background: #2563eb;
        }}
        .response {{
            background: #1f2937;
            color: #f3f4f6;
            padding: 15px;
            border-radius: 8px;
            margin-top: 10px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 0.9em;
            white-space: pre-wrap;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🐕 Boris & Fiona Walk Reminder Debug</h1>
        
        <div class="status-grid">
            <div class="status-card">
                <h3>Current Time (Eastern)</h3>
                <div class="status-value">{current_hour}:XX</div>
                <p>Hour: {current_hour}/24</p>
            </div>
            
            <div class="status-card">
                <h3>Walk Window</h3>
                <div class="status-value {walk_status_class}">{walk_status}</div>
                <p>Active: 2 PM - 6 PM (14-18)</p>
            </div>
            
            <div class="status-card">
                <h3>Already Reminded Today</h3>
                <div class="status-value {reminded_status_class}">{reminded_status}</div>
                <p>{reminded_detail}</p>
            </div>
            
            <div class="status-card">
                <h3>Next Action</h3>
                <div class="status-value">{next_action}</div>
                <p>{next_action_detail}</p>
            </div>
        </div>
        
        <div class="api-test">
            <h3>🧪 API Testing</h3>
            <p>Test the walk reminder logic:</p>
            <button onclick="testAPI()">Test /check Endpoint</button>
            <button onclick="location.reload()">Refresh Status</button>
            <div id="response"></div>
        </div>
        
        <div style="margin-top: 30px; text-align: center; opacity: 0.8;">
            <p>🎯 Target: $2.25/month SMS reminders | 💰 Compute: FREE (Spin Cloud)</p>
            <p>🏗️ Architecture: GitHub Actions → Spin WASM → Twilio SMS</p>
        </div>
    </div>
    
    <script>
        async function testAPI() {{
            const responseDiv = document.getElementById('response');
            responseDiv.innerHTML = 'Testing...';
            
            try {{
                const response = await fetch('/check', {{
                    method: 'POST'
                }});
                const data = await response.json();
                responseDiv.innerHTML = JSON.stringify(data, null, 2);
                responseDiv.className = 'response';
            }} catch (error) {{
                responseDiv.innerHTML = 'Error: ' + error.message;
                responseDiv.className = 'response';
            }}
        }}
    </script>
</body>
</html>
"#, 
        current_hour = current_hour,
        walk_status = if is_walk_time { "ACTIVE" } else { "INACTIVE" },
        walk_status_class = if is_walk_time { "status-good" } else { "status-warning" },
        reminded_status = if already_reminded { "YES" } else { "NO" },
        reminded_status_class = if already_reminded { "status-warning" } else { "status-good" },
        reminded_detail = if already_reminded { "Reminder sent today" } else { "Ready to send" },
        next_action = if !is_walk_time { 
            "WAIT" 
        } else if already_reminded { 
            "DONE" 
        } else { 
            "SEND SMS" 
        },
        next_action_detail = if !is_walk_time {
            format!("Wait for walk window ({}h until 14h)", if current_hour < 14 { 14 - current_hour } else { 24 - current_hour + 14 })
        } else if already_reminded {
            "Already reminded today".to_string()
        } else {
            "Ready to send walk reminder!".to_string()
        }
    );
    
    Ok(Response::builder()
        .status(200)
        .header("content-type", "text/html")
        .body(html)
        .build())
}

/// Core logic: check if we should send a reminder and do it
async fn check_and_send_reminder() -> Result<bool> {
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
    sms::send_walk_reminder(&message).await?;
    
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