use serde::Deserialize;
use anyhow::{anyhow, Result};
use spin_sdk::variables;

#[derive(Debug, Deserialize, Clone, PartialEq)]
pub struct Goal {
    pub slug: String,
    pub title: String,
    pub derail_risk: String,
}

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
        let today = chrono::Utc::now().format("%Y%m%d").to_string();
        Ok(datapoints.iter().any(|d| d.daystamp == today))
    } else {
        let error_body = String::from_utf8_lossy(response.body());
        Err(anyhow!("Beeminder API error {}: {}", response.status(), error_body))
    }
}

pub async fn get_all_goals() -> Result<Vec<Goal>> {
    let api_key = variables::get("beeminder_api_key")
        .map_err(|_| anyhow!("Missing beeminder_api_key variable"))?;
    let username = variables::get("beeminder_username")
        .map_err(|_| anyhow!("Missing beeminder_username variable"))?;
    
    let url = format!(
        "https://www.beeminder.com/api/v1/users/{}/goals.json?auth_token={}",
        username, api_key
    );

    let request = spin_sdk::http::Request::builder()
        .method(spin_sdk::http::Method::Get)
        .uri(&url)
        .build();

    let response: spin_sdk::http::Response = spin_sdk::http::send(request).await?;

    if *response.status() == 200 {
        let goals: Vec<Goal> = serde_json::from_slice(response.body())?;
        Ok(goals)
    } else {
        let error_body = String::from_utf8_lossy(response.body());
        Err(anyhow!("Beeminder API error {}: {}", response.status(), error_body))
    }
}

pub fn filter_urgent_goals(goals: Vec<Goal>) -> Vec<Goal> {
    goals.into_iter()
        .filter(|g| g.derail_risk == "WARNING" || g.derail_risk == "CRITICAL")
        .collect()
}

pub fn pick_pivot_goal(goals: Vec<Goal>) -> Option<Goal> {
    filter_urgent_goals(goals).into_iter().next()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pick_pivot_goal() {
        let goals = vec![
            Goal { slug: "urgent".into(), title: "Urgent".into(), derail_risk: "WARNING".into() },
        ];
        let pivot = pick_pivot_goal(goals);
        assert!(pivot.is_some());
        assert_eq!(pivot.unwrap().slug, "urgent");
    }

    #[test]
    fn test_urgent_goals_filtering() {
        let goals = vec![
            Goal { slug: "safe".into(), title: "Safe Goal".into(), derail_risk: "SAFE".into() },
            Goal { slug: "urgent".into(), title: "Urgent Goal".into(), derail_risk: "WARNING".into() },
            Goal { slug: "critical".into(), title: "Critical Goal".into(), derail_risk: "CRITICAL".into() },
        ];
        
        let urgent = filter_urgent_goals(goals);
        assert_eq!(urgent.len(), 2, "Should find WARNING and CRITICAL goals");
        assert!(urgent.iter().any(|g| g.slug == "urgent"));
        assert!(urgent.iter().any(|g| g.slug == "critical"));
    }
}
