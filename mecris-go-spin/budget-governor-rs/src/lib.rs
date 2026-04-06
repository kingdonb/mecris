use serde::{Deserialize, Serialize};
use spin_sdk::http::{IntoResponse, Request, Response, Method};
use spin_sdk::{http_component, variables, key_value::Store};
use chrono::{DateTime, Utc, Duration};
use std::collections::HashMap;

const ENVELOPE_WINDOW_MINUTES: i64 = 39;
const ENVELOPE_SPEND_RATIO: f64 = 0.05;

#[derive(Debug, Serialize, Deserialize, Clone)]
struct SpendEvent {
    bucket: String,
    cost: f64,
    ts: DateTime<Utc>,
}

#[derive(Debug, Serialize, Deserialize)]
struct BucketConfig {
    bucket_type: String,
    limit: f64,
}

struct BudgetGovernor {
    user_id: String,
    kv_store: Store,
    buckets: HashMap<String, BucketConfig>,
}

impl BudgetGovernor {
    fn new(user_id: String, store: Store) -> Self {
        let mut buckets = HashMap::new();
        buckets.insert("helix".to_string(), BucketConfig {
            bucket_type: "spend".to_string(),
            limit: variables::get("HELIX_CREDIT_LIMIT").unwrap_or("100.00".to_string()).parse().unwrap_or(100.0),
        });
        buckets.insert("gemini".to_string(), BucketConfig {
            bucket_type: "spend".to_string(),
            limit: variables::get("GEMINI_FREE_LIMIT").unwrap_or("50.00".to_string()).parse().unwrap_or(50.0),
        });
        buckets.insert("anthropic_api".to_string(), BucketConfig {
            bucket_type: "guard".to_string(),
            limit: variables::get("ANTHROPIC_BUDGET_LIMIT").unwrap_or("20.89".to_string()).parse().unwrap_or(20.89),
        });
        buckets.insert("groq".to_string(), BucketConfig {
            bucket_type: "guard".to_string(),
            limit: variables::get("GROQ_BUDGET_LIMIT").unwrap_or("10.00".to_string()).parse().unwrap_or(10.0),
        });

        Self { user_id, kv_store: store, buckets }
    }

    fn kv_key(&self) -> String {
        format!("budget_log_{}", self.user_id)
    }

    fn load_log(&self) -> Vec<SpendEvent> {
        match self.kv_store.get(self.kv_key()) {
            Ok(Some(bytes)) => serde_json::from_slice(&bytes).unwrap_or_default(),
            _ => Vec::new(),
        }
    }

    fn save_log(&self, log: &Vec<SpendEvent>) {
        let cutoff = Utc::now() - Duration::hours(24);
        let pruned: Vec<SpendEvent> = log.iter().filter(|e| e.ts >= cutoff).cloned().collect();
        if let Ok(bytes) = serde_json::to_vec(&pruned) {
            let _ = self.kv_store.set(self.kv_key(), &bytes);
        }
    }

    fn get_total_spent(&self, log: &[SpendEvent], bucket: &str) -> f64 {
        log.iter().filter(|e| e.bucket == bucket).map(|e| e.cost).sum()
    }

    fn get_window_spent(&self, log: &[SpendEvent], bucket: &str) -> f64 {
        let cutoff = Utc::now() - Duration::minutes(ENVELOPE_WINDOW_MINUTES);
        log.iter().filter(|e| e.bucket == bucket && e.ts >= cutoff).map(|e| e.cost).sum()
    }

    fn check_envelope(&self, log: &[SpendEvent], bucket: &str, cost: f64) -> String {
        let config = match self.buckets.get(bucket) {
            Some(c) => c,
            None => return "deny".to_string(),
        };

        if self.get_total_spent(log, bucket) >= config.limit {
            return "deny".to_string();
        }

        if self.get_window_spent(log, bucket) + cost > (ENVELOPE_SPEND_RATIO * config.limit) {
            return "defer".to_string();
        }

        "allow".to_string()
    }

    fn recommend_bucket(&self, log: &[SpendEvent]) -> String {
        let spend_avail: Vec<_> = self.buckets.iter()
            .filter(|(n, c)| c.bucket_type == "spend" && self.get_total_spent(log, n) < c.limit)
            .collect();

        if !spend_avail.is_empty() {
            return spend_avail.iter()
                .max_by(|a, b| (a.1.limit - self.get_total_spent(log, a.0))
                    .partial_cmp(&(b.1.limit - self.get_total_spent(log, b.0))).unwrap())
                .unwrap().0.clone();
        }

        let guard_avail: Vec<_> = self.buckets.iter()
            .filter(|(n, c)| c.bucket_type == "guard" && self.get_total_spent(log, n) < c.limit)
            .collect();

        if !guard_avail.is_empty() {
            return guard_avail.iter()
                .min_by(|a, b| (self.get_total_spent(log, a.0) / a.1.limit)
                    .partial_cmp(&(self.get_total_spent(log, b.0) / b.1.limit)).unwrap())
                .unwrap().0.clone();
        }

        self.buckets.keys().next().unwrap_or(&"anthropic_api".to_string()).clone()
    }
}

#[http_component]
async fn handle_budget_governor(req: Request) -> anyhow::Result<impl IntoResponse> {
    let query = req.uri().split('?').nth(1).unwrap_or("");
    let params: HashMap<String, String> = url::form_urlencoded::parse(query.as_bytes())
        .into_owned()
        .collect();

    let user_id = match params.get("user_id") {
        Some(id) => id.clone(),
        None => return Ok(Response::builder().status(400).body("user_id required").build()),
    };

    let store = Store::open_default()?;
    let gov = BudgetGovernor::new(user_id, store);
    let mut log = gov.load_log();

    let path = req.path();
    if path == "/internal/budget-status" {
        let mut buckets_report = HashMap::new();
        for (name, cfg) in &gov.buckets {
            let spent = gov.get_total_spent(&log, name);
            buckets_report.insert(name.clone(), serde_json::json!({
                "type": cfg.bucket_type,
                "limit": cfg.limit,
                "spent_total": spent,
                "spent_window": gov.get_window_spent(&log, name),
                "remaining": (cfg.limit - spent).max(0.0),
                "envelope": gov.check_envelope(&log, name, 0.01)
            }));
        }
        let report = serde_json::json!({
            "buckets": buckets_report,
            "recommendation": gov.recommend_bucket(&log),
            "window_minutes": ENVELOPE_WINDOW_MINUTES
        });
        return Ok(Response::builder().status(200).header("content-type", "application/json").body(report.to_string()).build());
    } 
    
    if path == "/internal/budget-gate" && req.method() == &Method::Post {
        let bucket = params.get("bucket").cloned().unwrap_or_default();
        let cost: f64 = params.get("cost").and_then(|c| c.parse().ok()).unwrap_or(0.01);
        let envelope = gov.check_envelope(&log, &bucket, cost);
        let res = serde_json::json!({
            "allowed": envelope != "deny",
            "envelope": envelope,
            "recommendation": gov.recommend_bucket(&log)
        });
        return Ok(Response::builder().status(200).header("content-type", "application/json").body(res.to_string()).build());
    }

    if path == "/internal/budget-record" && req.method() == &Method::Post {
        let bucket = params.get("bucket").cloned().unwrap_or_default();
        let cost: f64 = params.get("cost").and_then(|c| c.parse().ok()).unwrap_or(0.0);
        log.push(SpendEvent { bucket, cost, ts: Utc::now() });
        gov.save_log(&log);
        return Ok(Response::builder().status(200).body("recorded").build());
    }

    Ok(Response::builder().status(404).build())
}
