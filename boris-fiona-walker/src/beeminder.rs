use serde::Deserialize;
use anyhow::{anyhow, Result};
use spin_sdk::variables;

#[derive(Debug, Deserialize)]
pub struct Datapoint {
    pub daystamp: String,
    pub value: f64,
    pub comment: String,
}

pub async fn has_walked_today(goal_slug: &str) -> Result<bool> {
    let api_key = variables::get("beeminder_api_key")
        .map_err(|_| anyhow!("Missing beeminder_api_key variable"))?;
    let username = variables::get("beeminder_username")
        .map_err(|_| anyhow!("Missing beeminder_username variable"))?;
    
    // Get today's date in Beeminder format (YYYYMMDD) or just check recent datapoints
    // For simplicity, we'll fetch the last few datapoints and check the date
    let url = format!(
        "https://www.beeminder.com/api/v1/users/{}/goals/{}/datapoints.json?auth_token={}&count=5",
        username, goal_slug, api_key
    );

    let request = spin_sdk::http::Request::builder()
        .method(spin_sdk::http::Method::Get)
        .uri(&url)
        .build();

    let response: spin_sdk::http::Response = spin_sdk::http::send(request).await?;

    if *response.status() == 200 {
        let datapoints: Vec<Datapoint> = serde_json::from_slice(response.body())?;
        
        // Check if any datapoint is from today (Eastern time)
        // We'll use the date from our time module
        let today = chrono::Utc::now().format("%Y%m%d").to_string();
        
        Ok(datapoints.iter().any(|d| d.daystamp == today))
    } else {
        let error_body = String::from_utf8_lossy(response.body());
        Err(anyhow!("Beeminder API error {}: {}", response.status(), error_body))
    }
}
