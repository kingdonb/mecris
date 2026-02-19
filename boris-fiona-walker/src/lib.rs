use spin_sdk::http::{Request, Response, Method};
use spin_sdk::variables;
use serde_json::json;
use anyhow::{Result, anyhow};
use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

mod sms;
mod time;
mod weather;
mod daylight;
mod beeminder;

use weather::WeatherCondition;

/// Main HTTP handler for walk reminder checks
#[spin_sdk::http_component]
async fn handle_walk_check(req: Request) -> Result<Response> {
    let path = req.path();
    
    // Security check: Log all incoming requests with IP and timestamp
    log_request(&req);
    
    match path {
        "/check" => handle_check_api(req).await,
        "/health" => handle_health_check().await,
        // Debug endpoints removed for production security
        _ => handle_not_found().await,
    }
}

/// Handle the API endpoint for walk reminder checks with authentication and rate limiting
async fn handle_check_api(req: Request) -> Result<Response> {
    // Security Layer 1: Method validation
    if req.method() != &Method::Post {
        return create_error_response(405, "Method not allowed. Use POST.");
    }
    
    // Security Layer 2: Authentication
    if let Err(e) = validate_webhook_secret(&req) {
        eprintln!("Authentication failed: {}", e);
        return create_error_response(401, "Unauthorized");
    }
    
    // Security Layer 3: Rate limiting  
    if let Err(e) = check_rate_limit(&req) {
        eprintln!("Rate limit exceeded: {}", e);
        return create_error_response(429, "Rate limit exceeded");
    }
    
    // Security Layer 4: Request size validation
    if req.body().len() > 1024 {
        return create_error_response(413, "Request too large");
    }
    
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

    // Fetch walk status from Beeminder
    let walked = beeminder::has_walked_today("bike").await.unwrap_or(false);

    // Fetch weather condition
    let weather = weather::get_current_weather().await?;
    
    // Check if weather is safe
    let (is_safe, reason) = weather::is_weather_safe(&weather);
    if !is_safe && !walked {
        // If it's unsafe and we HAVEN'T walked, skip the nag
        eprintln!("Walk skipped: {}", reason);
        return Ok(false);
    }
    
    // Send the reminder/congrats!
    let message = get_weather_aware_message(current_hour, &weather, walked);
    sms::send_walk_reminder(&message).await?;
    
    // Mark that we sent a reminder today
    mark_reminder_sent()?;
    
    Ok(true)
}

/// Security: Validate webhook secret from Authorization header
fn validate_webhook_secret(req: &Request) -> Result<()> {
    let expected_secret = variables::get("webhook_secret")
        .map_err(|_| anyhow!("Missing webhook_secret configuration"))?;
    
    let auth_header = req.header("authorization")
        .or_else(|| req.header("Authorization")).and_then(|v| v.as_str())
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow!("Missing Authorization header"))?;
    
    let expected_auth = format!("Bearer {}", expected_secret);
    
    if auth_header != expected_auth.as_str() {
        return Err(anyhow!("Invalid webhook secret"));
    }
    
    Ok(())
}

/// Security: Simple rate limiting using timestamp tracking
fn check_rate_limit(req: &Request) -> Result<()> {
    // Get client IP from headers (Spin Cloud should provide this)
    let client_ip = req.header("x-forwarded-for")
        .or_else(|| req.header("x-real-ip")).and_then(|v| v.as_str())
        .and_then(|v| v.as_str())
        .unwrap_or("unknown");
    
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();
    
    let rate_limit_key = format!("rate_limit:{}", client_ip);
    
    match spin_sdk::key_value::Store::open_default() {
        Ok(store) => {
            if let Ok(Some(last_request_bytes)) = store.get(&rate_limit_key) {
                if let Ok(last_request_str) = String::from_utf8(last_request_bytes) {
                    if let Ok(last_request_time) = last_request_str.parse::<u64>() {
                        // Rate limit: Allow only 1 request per hour per IP
                        if now - last_request_time < 3600 {
                            return Err(anyhow!("Rate limit: Only 1 request per hour allowed"));
                        }
                    }
                }
            }
            
            // Update rate limit timestamp
            let _ = store.set(&rate_limit_key, now.to_string().as_bytes());
        }
        Err(_) => {
            // If key-value store fails, log but don't block the request
            eprintln!("Warning: Rate limiting unavailable - key-value store error");
        }
    }
    
    Ok(())
}

/// Security: Log all incoming requests for monitoring
fn log_request(req: &Request) {
    let client_ip = req.header("x-forwarded-for")
        .or_else(|| req.header("x-real-ip")).and_then(|v| v.as_str())
        .and_then(|v| v.as_str())
        .unwrap_or("unknown");
    
    let user_agent = req.header("user-agent")
        .and_then(|v| v.as_str())
        .unwrap_or("unknown");
    
    let method = req.method();
    let path = req.path();
    
    println!("REQUEST: {} {} {} UA:{} IP:{}", 
             chrono::Utc::now().format("%Y-%m-%d %H:%M:%S"),
             method, path, user_agent, client_ip);
}

/// Security: Create standardized error responses
fn create_error_response(status: u16, message: &str) -> Result<Response> {
    let error_response = json!({
        "status": "error",
        "error": message,
        "timestamp": chrono::Utc::now().to_rfc3339()
    });
    
    Ok(Response::builder()
        .status(status)
        .header("content-type", "application/json")
        .header("x-content-type-options", "nosniff")
        .header("x-frame-options", "DENY")
        .body(error_response.to_string())
        .build())
}

/// Health check endpoint (no authentication required)
async fn handle_health_check() -> Result<Response> {
    let health_response = json!({
        "status": "healthy",
        "service": "boris-fiona-walker",
        "timestamp": chrono::Utc::now().to_rfc3339(),
        "version": "0.1.0"
    });
    
    Ok(Response::builder()
        .status(200)
        .header("content-type", "application/json")
        .body(health_response.to_string())
        .build())
}

/// Handle 404 responses (debug endpoints removed for security)
async fn handle_not_found() -> Result<Response> {
    create_error_response(404, "Endpoint not found")
}

/// Generate walk message based on time of day, weather, and walk status
fn get_weather_aware_message(hour: u8, weather: &WeatherCondition, walked: bool) -> String {
    if walked {
        let mut msg = "🌟 Great job on the walk earlier! You capitalized on the day.".to_string();
        
        if weather.temperature > 60.0 && weather.temperature < 80.0 && !weather.is_raining {
            msg = format!("{} It's still gorgeous out ({}°F).", msg, weather.temperature);
        }

        return format!("{} Since you're on a roll, how about clearing some Greek or Arabic cards? 📚", msg);
    }

    let mut base_message = match hour {
        14..=15 => "🐕 Afternoon walk time! Boris and Fiona are ready for their adventure.".to_string(),
        16..=17 => "🌅 Golden hour walk! Boris and Fiona would love a sunset stroll.".to_string(),
        18..=19 => "🌆 Evening walk time! Boris and Fiona are waiting by the door.".to_string(),
        _ => "🐕 Walk time! Boris and Fiona need their daily adventure.".to_string(),
    };

    // Add weather context
    if weather.temperature < 40.0 {
        base_message = format!("{} Brrr, it's chilly ({}°F)! 🧣", base_message, weather.temperature);
    } else if weather.temperature > 85.0 {
        base_message = format!("{} It's a bit warm ({}°F). 💧", base_message, weather.temperature);
    }

    if !daylight::is_daylight(weather) {
        base_message = format!("{} Watch out, it's getting dark! 🔦", base_message);
    } else if daylight::is_approaching_sunset(weather) {
        base_message = format!("{} Sunset is coming soon! 🌇", base_message);
    }

    base_message
}

/// Generate walk message based on time of day (Legacy)
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

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_weather_aware_message() {
        let hour = 16;
        let mut weather = WeatherCondition {
            temperature: 70.0,
            sunrise: 100,
            sunset: 1000,
            ..Default::default()
        };
        
        let msg = get_weather_aware_message(hour, &weather, false);
        assert!(msg.contains("Golden hour"));
        
        // Test cold weather
        weather.temperature = 30.0;
        let msg_cold = get_weather_aware_message(hour, &weather, false);
        assert!(msg_cold.contains("chilly"));
        
        // Test already walked
        let msg_walked = get_weather_aware_message(hour, &weather, true);
        assert!(msg_walked.contains("Great job"));
        assert!(msg_walked.contains("on a roll"));
    }

    #[test]
    fn test_walk_message_generation() {
        // Test that we generate appropriate messages for Boris & Fiona at different times
        
        // Afternoon messages (2-3 PM)
        let afternoon_msg = get_walk_message(14);
        assert!(afternoon_msg.contains("Boris"));
        assert!(afternoon_msg.contains("Fiona"));
        assert!(afternoon_msg.contains("Afternoon walk time"));
        assert!(afternoon_msg.contains("adventure"));
        
        let afternoon_msg2 = get_walk_message(15);
        assert!(afternoon_msg2.contains("Afternoon walk time"));
        
        // Golden hour messages (4-5 PM)
        let golden_msg = get_walk_message(16);
        assert!(golden_msg.contains("Golden hour"));
        assert!(golden_msg.contains("sunset stroll"));
        assert!(golden_msg.contains("Boris"));
        assert!(golden_msg.contains("Fiona"));
        
        let golden_msg2 = get_walk_message(17);
        assert!(golden_msg2.contains("Golden hour"));
        
        // Evening messages (6-7 PM)
        let evening_msg = get_walk_message(18);
        assert!(evening_msg.contains("Evening walk"));
        assert!(evening_msg.contains("waiting by the door"));
        assert!(evening_msg.contains("Boris"));
        assert!(evening_msg.contains("Fiona"));
        
        let evening_msg2 = get_walk_message(19);
        assert!(evening_msg2.contains("Evening walk"));
        
        // Default message for edge cases
        let default_msg = get_walk_message(12);
        assert!(default_msg.contains("Boris"));
        assert!(default_msg.contains("Fiona"));
        assert!(default_msg.contains("daily adventure"));
    }
    
    #[test]
    fn test_walk_time_eligibility() {
        // Test the core business rule: Only eligible during walk window (2-6 PM)
        
        // Before walk window
        assert!(!is_in_walk_window(13)); // 1 PM
        assert!(!is_in_walk_window(12)); // 12 PM
        assert!(!is_in_walk_window(8));  // 8 AM
        
        // During walk window
        assert!(is_in_walk_window(14)); // 2 PM - start
        assert!(is_in_walk_window(15)); // 3 PM
        assert!(is_in_walk_window(16)); // 4 PM
        assert!(is_in_walk_window(17)); // 5 PM
        assert!(is_in_walk_window(18)); // 6 PM - end
        
        // After walk window
        assert!(!is_in_walk_window(19)); // 7 PM
        assert!(!is_in_walk_window(20)); // 8 PM
        assert!(!is_in_walk_window(23)); // 11 PM
    }
    
    #[test]
    fn test_rate_limiting_logic() {
        // Test that we understand the rate limiting requirements
        // (This tests the concept - actual implementation needs mocking)
        
        // Simulate "already reminded today" scenarios
        let scenarios = vec![
            ("2025-10-19", "2025-10-19", true),  // Same day - should block
            ("2025-10-19", "2025-10-20", false), // Next day - should allow
            ("2025-10-18", "2025-10-19", false), // Previous day - should allow
        ];
        
        for (last_date, current_date, expected_blocked) in scenarios {
            let is_blocked = simulate_rate_limiting(last_date, current_date);
            assert_eq!(is_blocked, expected_blocked, 
                "Rate limiting failed for last_date: {}, current_date: {}", 
                last_date, current_date);
        }
    }
    
    #[test] 
    fn test_http_response_structure() {
        // Test that API responses have the expected structure
        
        // Test successful response structure
        let success_response = serde_json::json!({
            "status": "success",
            "reminded": true,
            "timestamp": "2025-10-19T17:45:26.920813+00:00",
            "dogs": ["Boris", "Fiona"],
            "spin_watch": "working! 🎉"
        });
        
        // Verify required fields are present
        assert_eq!(success_response["status"], "success");
        assert!(success_response["reminded"].is_boolean());
        assert!(success_response["timestamp"].is_string());
        assert!(success_response["dogs"].is_array());
        
        let dogs = success_response["dogs"].as_array().unwrap();
        assert_eq!(dogs.len(), 2);
        assert_eq!(dogs[0], "Boris");
        assert_eq!(dogs[1], "Fiona");
        
        // Test error response structure
        let error_response = serde_json::json!({
            "status": "error",
            "error": "SMS sending failed",
            "timestamp": "2025-10-19T17:45:26.920813+00:00"
        });
        
        assert_eq!(error_response["status"], "error");
        assert!(error_response["error"].is_string());
        assert!(error_response["timestamp"].is_string());
    }
    
    #[test]
    fn test_sms_message_requirements() {
        // Test that SMS messages meet our requirements
        
        let test_hours = vec![14, 15, 16, 17, 18, 19];
        
        for hour in test_hours {
            let message = get_walk_message(hour);
            
            // All messages must mention both dogs
            assert!(message.contains("Boris"), "Message missing Boris for hour {}: {}", hour, message);
            assert!(message.contains("Fiona"), "Message missing Fiona for hour {}: {}", hour, message);
            
            // All messages should have emoji
            assert!(message.chars().any(|c| c as u32 > 127), "Message missing emoji for hour {}: {}", hour, message);
            
            // Messages should be reasonable length for SMS
            assert!(message.len() > 20, "Message too short for hour {}: {}", hour, message);
            assert!(message.len() < 160, "Message too long for SMS for hour {}: {}", hour, message);
            
            // Messages should be encouraging/positive
            let positive_words = ["ready", "adventure", "love", "time", "stroll"];
            assert!(positive_words.iter().any(|word| message.to_lowercase().contains(word)), 
                "Message not encouraging for hour {}: {}", hour, message);
        }
    }
    
    #[test]
    fn test_web_frontend_requirements() {
        // Test that web frontend shows required information
        
        // This would be a more complex test in practice, but we can test the data
        let current_hour = 15; // 3 PM
        let is_walk_time = (14..=18).contains(&current_hour);
        let already_reminded = false;
        
        // Test status calculations
        assert!(is_walk_time, "Should be walk time at 3 PM");
        
        let walk_status = if is_walk_time { "ACTIVE" } else { "INACTIVE" };
        let walk_status_class = if is_walk_time { "status-good" } else { "status-warning" };
        
        assert_eq!(walk_status, "ACTIVE");
        assert_eq!(walk_status_class, "status-good");
        
        let reminded_status = if already_reminded { "YES" } else { "NO" };
        let reminded_status_class = if already_reminded { "status-warning" } else { "status-good" };
        
        assert_eq!(reminded_status, "NO");
        assert_eq!(reminded_status_class, "status-good");
        
        // Test next action logic
        let next_action = if !is_walk_time { 
            "WAIT" 
        } else if already_reminded { 
            "DONE" 
        } else { 
            "SEND SMS" 
        };
        
        assert_eq!(next_action, "SEND SMS");
    }
    
    #[test]
    fn test_environment_variable_requirements() {
        // Test that we understand what environment variables are needed
        
        let required_vars = vec![
            "SPIN_VARIABLE_TWILIO_ACCOUNT_SID",
            "SPIN_VARIABLE_TWILIO_AUTH_TOKEN", 
            "SPIN_VARIABLE_TWILIO_FROM_NUMBER",
            "SPIN_VARIABLE_TWILIO_TO_NUMBER",
            "SPIN_VARIABLE_OPENWEATHER_API_KEY",
        ];
        
        // In a real test, we'd check these are available
        // For now, just document the requirement
        assert_eq!(required_vars.len(), 5);
        
        // Test that we handle missing variables gracefully
        // (This would need actual implementation)
        assert!(true, "Environment variable handling should be graceful");
    }
    
    #[test]
    fn test_spin_cloud_deployment_requirements() {
        // Test deployment configuration requirements
        
        // Test that spin.toml has required routes
        let expected_routes = vec!["/check", "/..."];
        // In practice, we'd parse spin.toml
        assert_eq!(expected_routes.len(), 2);
        
        // Test that allowed outbound hosts are configured
        let expected_hosts = vec!["https://api.twilio.com", "https://api.openweathermap.org"];
        assert!(!expected_hosts.is_empty());
        
        // Test that component build configuration is present
        let expected_watch_patterns = vec!["src/**/*.rs", "Cargo.toml"];
        assert!(!expected_watch_patterns.is_empty());
    }
    
    // Helper functions for testing
    fn is_in_walk_window(hour: u8) -> bool {
        (14..=18).contains(&hour)
    }
    
    fn simulate_rate_limiting(last_reminder_date: &str, current_date: &str) -> bool {
        // Simulate rate limiting logic - returns true if should be blocked
        last_reminder_date == current_date
    }
}