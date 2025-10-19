use spin_sdk::variables;
use anyhow::{anyhow, Result};
use serde_json::json;

/// Send SMS walk reminder via Twilio
pub fn send_walk_reminder(message: &str) -> Result<()> {
    let account_sid = variables::get("twilio_account_sid")
        .map_err(|_| anyhow!("Missing twilio_account_sid variable"))?;
    let auth_token = variables::get("twilio_auth_token")
        .map_err(|_| anyhow!("Missing twilio_auth_token variable"))?;
    let from_number = variables::get("twilio_from_number")
        .map_err(|_| anyhow!("Missing twilio_from_number variable"))?;
    let to_number = variables::get("twilio_to_number")
        .map_err(|_| anyhow!("Missing twilio_to_number variable"))?;
    
    // Twilio API endpoint
    let url = format!("https://api.twilio.com/2010-04-01/Accounts/{}/Messages.json", account_sid);
    
    // Prepare the request body
    let body = format!(
        "From={}&To={}&Body={}",
        urlencoding::encode(&from_number),
        urlencoding::encode(&to_number),
        urlencoding::encode(message)
    );
    
    // Send the HTTP request
    let request = spin_sdk::http::Request::builder()
        .method("POST")
        .uri(&url)
        .header("Content-Type", "application/x-www-form-urlencoded")
        .header("Authorization", format!("Basic {}", encode_basic_auth(&account_sid, &auth_token)))
        .body(body.into_bytes())?;
    
    let response = spin_sdk::http::send(request)?;
    
    if response.status().as_u16() >= 200 && response.status().as_u16() < 300 {
        println!("SMS sent successfully: {}", message);
        Ok(())
    } else {
        let error_body = String::from_utf8_lossy(response.body());
        Err(anyhow!("Twilio API error {}: {}", response.status(), error_body))
    }
}

/// Encode basic authentication for Twilio
fn encode_basic_auth(username: &str, password: &str) -> String {
    use base64::Engine;
    let credentials = format!("{}:{}", username, password);
    base64::engine::general_purpose::STANDARD.encode(credentials.as_bytes())
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_basic_auth_encoding() {
        let encoded = encode_basic_auth("user", "pass");
        assert!(!encoded.is_empty());
    }
}