use serde::{Deserialize, Serialize};
use spin_sdk::http::{IntoResponse, Request, Response};
use spin_sdk::{http_component, variables, pg::{Connection, ParameterValue, DbValue}};
use chrono::{DateTime, Utc, Timelike};
use chrono_tz::America::New_York as EASTERN;
use std::collections::HashMap;

const TIER2_IDLE_HOURS: f64 = 6.0;

#[derive(Serialize, Deserialize, Debug)]
struct NagResult {
    should_send: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    msg_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tier: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    message: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    reason: Option<String>,
}

struct NagEngine {
    user_id: String,
    db_url: String,
}

impl NagEngine {
    fn new(user_id: String, db_url: String) -> Self {
        Self { user_id, db_url }
    }

    fn get_conn(&self) -> anyhow::Result<Connection> {
        Ok(Connection::open(&self.db_url)?)
    }

    fn get_hours_since_last(&self, conn: &Connection, msg_type: Option<&str>) -> f64 {
        let query = "SELECT sent_at FROM message_log WHERE user_id = $1 AND (type = $2 OR $2 IS NULL) ORDER BY sent_at DESC LIMIT 1";
        let params = vec![
            ParameterValue::Str(self.user_id.clone()),
            match msg_type { Some(t) => ParameterValue::Str(t.to_string()), None => ParameterValue::DbNull }
        ];
        
        match conn.query(query, &params) {
            Ok(rs) if !rs.rows.is_empty() => {
                let sent_at_str = match &rs.rows[0][0] { DbValue::Str(s) => s.clone(), _ => return 999.0 };
                // Simple parse for ISO8601-like string from Postgres
                if let Ok(sent_at) = DateTime::parse_from_rfc3339(&sent_at_str.replace(" ", "T")) {
                    let now = Utc::now();
                    return (now.with_timezone(&sent_at.timezone()) - sent_at).num_minutes() as f64 / 60.0;
                }
                999.0
            }
            _ => 999.0
        }
    }

    fn parse_runway_hours(&self, runway: &str) -> f64 {
        let parts: Vec<&str> = runway.to_lowercase().split_whitespace().collect();
        if parts.len() >= 2 && parts[1].contains("hour") {
            return parts[0].parse().unwrap_or(999.0);
        }
        999.0
    }

    async fn check_reminders(&self) -> anyhow::Result<NagResult> {
        let conn = self.get_conn()?;

        // 1. Global Rate Limit (30m)
        if self.get_hours_since_last(&conn, None) < 0.5 {
            return Ok(NagResult { should_send: false, msg_type: None, tier: None, message: None, reason: Some("Global rate limit".to_string()) });
        }

        let now_eastern = Utc::now().with_timezone(&EASTERN);
        let hour = now_eastern.hour();

        // 2. Fetch Alerts
        let alerts_query = "SELECT slug, title, runway, derail_risk FROM beeminder_alerts WHERE user_id = $1";
        let alerts_rs = conn.query(alerts_query, &[ParameterValue::Str(self.user_id.clone())])?;
        
        // 3. Tier 3: Critical Runway (< 2h)
        for row in &alerts_rs.rows {
            let runway = match &row[2] { DbValue::Str(s) => s.clone(), _ => "".to_string() };
            let title = match &row[1] { DbValue::Str(s) => s.clone(), _ => "Goal".to_string() };
            if self.parse_runway_hours(&runway) < 2.0 {
                if self.get_hours_since_last(&conn, Some("beeminder_emergency_tier3")) >= 1.0 {
                    return Ok(NagResult {
                        should_send: true,
                        msg_type: Some("beeminder_emergency_tier3".to_string()),
                        tier: Some(3),
                        message: Some(format!("🚨🚨🚨 CRITICAL EMERGENCY: {} derails in under 2 hours — TAKE ACTION NOW.", title)),
                        reason: None,
                    });
                }
            }
        }

        // 4. Emergency Sleep Window (12am-8am)
        if hour < 8 {
            return Ok(NagResult { should_send: false, msg_type: None, tier: None, message: None, reason: Some("Emergency sleep window".to_string()) });
        }

        // 5. Language Emergencies
        let arabic_alert = alerts_rs.rows.iter().find(|r| {
            let slug = match &r[0] { DbValue::Str(s) => s.clone(), _ => "".to_string() };
            let risk = match &r[3] { DbValue::Str(s) => s.clone(), _ => "".to_string() };
            slug == "reviewstack" && risk == "CRITICAL"
        });

        if let Some(row) = arabic_alert {
            let hours_since = self.get_hours_since_last(&conn, Some("arabic_review_reminder"));
            if hours_since >= 2.0 {
                let runway = match &row[2] { DbValue::Str(s) => s.clone(), _ => "0 days".to_string() };
                if hours_since >= TIER2_IDLE_HOURS {
                    return Ok(NagResult {
                        should_send: true,
                        msg_type: Some("arabic_review_reminder".to_string()),
                        tier: Some(2),
                        message: Some(format!("🚨 ESCALATED: Arabic reviews still overdue after {:.0}h. reviewstack won't fix itself — open Clozemaster NOW. 📚", hours_since)),
                        reason: None,
                    });
                }
                return Ok(NagResult {
                    should_send: true,
                    msg_type: Some("arabic_review_reminder".to_string()),
                    tier: Some(1),
                    message: Some(format!("🚨 Arabic reviews are CRITICAL — you have {} remaining. Open Clozemaster NOW!", runway)),
                    reason: None,
                });
            }
        }

        // 6. Normal Sleep Window (8pm-8am)
        if hour >= 20 {
            return Ok(NagResult { should_send: false, msg_type: None, tier: None, message: None, reason: Some("Normal sleep window".to_string()) });
        }

        // 7. Walk Reminders (2pm-6pm)
        if (14..=18).contains(&hour) {
            let walk_query = "SELECT COUNT(*) FROM walk_inferences WHERE user_id = $1 AND (start_time::TIMESTAMPTZ AT TIME ZONE 'US/Eastern')::DATE = (CURRENT_TIMESTAMP AT TIME ZONE 'US/Eastern')::DATE AND CAST(step_count AS INTEGER) >= 2000";
            let walk_rs = conn.query(walk_query, &[ParameterValue::Str(self.user_id.clone())])?;
            let has_walked = match &walk_rs.rows[0][0] { DbValue::Int64(i) => *i > 0, _ => false };

            if !has_walked {
                let hours_since = self.get_hours_since_last(&conn, Some("walk_reminder"));
                if hours_since >= 2.5 {
                    if hours_since >= TIER2_IDLE_HOURS {
                        return Ok(NagResult {
                            should_send: true,
                            msg_type: Some("walk_reminder".to_string()),
                            tier: Some(2),
                            message: Some(format!("⚠️ Still no walk after {:.0}h. Boris and Fiona are not impressed. Get outside NOW. 🐕🚨", hours_since)),
                            reason: None,
                        });
                    }
                    return Ok(NagResult {
                        should_send: true,
                        msg_type: Some("walk_reminder".to_string()),
                        tier: Some(1),
                        message: Some("🐕 Afternoon walk time! Boris and Fiona are ready for their adventure. 🌅".to_string()),
                        reason: None,
                    });
                }
            }
        }

        Ok(NagResult { should_send: false, msg_type: None, tier: None, message: None, reason: Some("No conditions met".to_string()) })
    }
}

#[http_component]
async fn handle_nag_engine(req: Request) -> anyhow::Result<impl IntoResponse> {
    let query = req.uri().split('?').nth(1).unwrap_or("");
    let params: HashMap<String, String> = url::form_urlencoded::parse(query.as_bytes()).into_owned().collect();

    let user_id = match params.get("user_id") {
        Some(id) => id.clone(),
        None => return Ok(Response::builder().status(400).body("user_id required").build()),
    };

    let db_url = variables::get("db_url")?;
    let engine = NagEngine::new(user_id, db_url);
    let result = engine.check_reminders().await?;

    Ok(Response::builder()
        .status(200)
        .header("content-type", "application/json")
        .body(serde_json::to_string(&result)?)
        .build())
}
