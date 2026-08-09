//! Twilio watcher - event-driven balance monitoring via webhook

use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{info, warn};
use warp::Filter;

use crate::budget::budget_ledger::{BudgetLedger, TwilioProjection};

/// Twilio webhook payload (incoming from Twilio)
#[derive(Debug, Clone, Deserialize)]
pub struct TwilioWebhookPayload {
    #[serde(rename = "AccountSid")]
    pub account_sid: String,
    #[serde(rename = "Balance")]
    pub balance: String,
    #[serde(rename = "Currency")]
    pub currency: String,
}

/// Twilio watcher configuration
#[derive(Debug, Clone)]
pub struct TwilioWatcherConfig {
    pub webhook_port: u16,
    pub webhook_path: String,
    pub low_balance_threshold: f64,
    pub auth_token: Option<String>,
}

impl Default for TwilioWatcherConfig {
    fn default() -> Self {
        Self {
            webhook_port: 8081,
            webhook_path: "/webhook/twilio".to_string(),
            low_balance_threshold: 5.0,
            auth_token: None,
        }
    }
}

/// Twilio watcher - receives webhooks and updates ledger
pub struct TwilioWatcher {
    ledger: Arc<BudgetLedger>,
    config: TwilioWatcherConfig,
    latest_balance: Arc<RwLock<Option<f64>>>,
    latest_monthly_burn: Arc<RwLock<f64>>,
}

impl TwilioWatcher {
    pub fn new(ledger: Arc<BudgetLedger>, config: TwilioWatcherConfig) -> Self {
        Self {
            ledger,
            config,
            latest_balance: Arc::new(RwLock::new(None)),
            latest_monthly_burn: Arc::new(RwLock::new(2.3)),
        }
    }

    /// Starts the webhook server
    pub async fn start(&self) -> anyhow::Result<()> {
        let ledger = self.ledger.clone();
        let latest_balance = self.latest_balance.clone();
        let latest_monthly_burn = self.latest_monthly_burn.clone();
        let webhook_path = self.config.webhook_path.clone();
        let webhook_port = self.config.webhook_port;
        let low_threshold = self.config.low_balance_threshold;

        let webhook_path_owned = webhook_path.trim_start_matches('/').to_string();
        let webhook_route = warp::path(webhook_path_owned)
            .and(warp::post())
            .and(warp::body::form())
            .and_then(move |payload: TwilioWebhookPayload| {
                let ledger = ledger.clone();
                let latest_balance = latest_balance.clone();
                let latest_monthly_burn = latest_monthly_burn.clone();
                let low_threshold = low_threshold;

                async move {
                    let balance: f64 = payload.balance.parse().unwrap_or(0.0);
                    
                    *latest_balance.write().await = Some(balance);
                    
                    let ledger_clone = ledger.clone();
                    let monthly_burn = *latest_monthly_burn.read().await;
                    tokio::task::spawn_blocking(move || {
                        ledger_clone.upsert_twilio_balance(balance, monthly_burn)
                    }).await.unwrap().ok();
                    
                    info!("Twilio webhook received: balance = ${:.2}", balance);
                    
                    if balance < low_threshold {
                        warn!("TWILIO LOW BALANCE ALERT: ${:.2} (threshold: ${:.2})", balance, low_threshold);
                    }
                    
                    Ok::<_, warp::Rejection>(warp::reply::json(&serde_json::json!({"status": "ok"})))
                }
            });

        let addr = ([0, 0, 0, 0], webhook_port);
        info!("Starting Twilio webhook server on {:?} {}", addr, webhook_path);
        
        tokio::spawn(async move {
            warp::serve(webhook_route).run(addr).await;
        });

        Ok(())
    }

    /// Gets current Twilio projection
    pub async fn get_projection(&self) -> TwilioProjection {
        let balance = *self.latest_balance.read().await;
        let monthly_burn = *self.latest_monthly_burn.read().await;
        
        if let Some(bal) = balance {
            let projected_exhaustion = if monthly_burn > 0.0 {
                let months_remaining = bal / monthly_burn;
                Some(Utc::now() + Duration::days((months_remaining * 30.0) as i64))
            } else {
                None
            };
            
            TwilioProjection {
                balance: bal,
                monthly_burn,
                projected_exhaustion,
            }
        } else {
            let ledger = self.ledger.clone();
            tokio::task::spawn_blocking(move || ledger.get_twilio_projection())
                .await
                .unwrap()
                .unwrap_or_default()
        }
    }

    /// Updates monthly burn rate estimate
    pub async fn update_monthly_burn(&self, burn: f64) {
        *self.latest_monthly_burn.write().await = burn;
    }
}

/// Default implementation for TwilioProjection
impl Default for TwilioProjection {
    fn default() -> Self {
        Self {
            balance: 0.0,
            monthly_burn: 0.0,
            projected_exhaustion: None,
        }
    }
}

/// HTTP endpoint handler for GET /budget/twilio
pub async fn handle_twilio_budget_get(
    ledger: Arc<BudgetLedger>,
) -> Result<impl warp::Reply, warp::Rejection> {
    let projection = tokio::task::spawn_blocking(move || ledger.get_twilio_projection())
        .await
        .unwrap()
        .unwrap_or_default();
    Ok(warp::reply::json(&projection))
}

/// Creates the budget API routes
pub fn budget_routes(ledger: Arc<BudgetLedger>) -> impl Filter<Extract = impl warp::Reply, Error = warp::Rejection> + Clone {
    let ledger_clone = ledger.clone();
    let twilio_route = warp::path("budget")
        .and(warp::path("twilio"))
        .and(warp::get())
        .and(warp::any().map(move || ledger_clone.clone()))
        .and_then(handle_twilio_budget_get);
    
    twilio_route
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::budget::budget_ledger::BudgetLedger;

    #[tokio::test]
    async fn test_twilio_projection() {
        let ledger = Arc::new(BudgetLedger::new_in_memory().unwrap());
        let config = TwilioWatcherConfig::default();
        let watcher = TwilioWatcher::new(ledger.clone(), config);

        ledger.upsert_twilio_balance(4.60, 2.3).unwrap();
        
        let projection = watcher.get_projection().await;
        assert_eq!(projection.balance, 4.60);
        assert_eq!(projection.monthly_burn, 2.3);
        assert!(projection.projected_exhaustion.is_some());
        
        let days = (projection.projected_exhaustion.unwrap() - Utc::now()).num_days();
        assert!((55..=65).contains(&days));
    }
}