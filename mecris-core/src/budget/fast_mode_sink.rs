//! Fast mode sink - routes to local Gemma/Ollama

use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde_json::json;
use uuid::Uuid;

use crate::budget::expiry_policy::{Budget, BudgetId};
use crate::budget::sink_registry::{Sink, SinkMode, SpendRecord, Task, TaskStage};

/// Fast mode sink using local Ollama (Gemma)
/// For breadth tasks: research, summarization, codegen drafts
pub struct FastModeSink {
    ollama_endpoint: String,
    model: String,
    http_client: reqwest::Client,
}

impl FastModeSink {
    pub fn new(ollama_endpoint: impl Into<String>, model: impl Into<String>) -> Self {
        Self {
            ollama_endpoint: ollama_endpoint.into(),
            model: model.into(),
            http_client: reqwest::Client::new(),
        }
    }

    /// Default constructor for local Ollama
    pub fn default_local() -> Self {
        Self::new("http://localhost:11434", "gemma:2b")
    }

    /// Checks if Ollama is available
    pub async fn is_available(&self) -> bool {
        let url = format!("{}/api/tags", self.ollama_endpoint);
        self.http_client
            .get(&url)
            .send()
            .await
            .map(|r| r.status().is_success())
            .unwrap_or(false)
    }
}

#[async_trait]
impl Sink for FastModeSink {
    fn can_absorb(&self, budget: &Budget, task: &Task) -> bool {
        // Can absorb if:
        // 1. Budget prefers fast mode or auto
        // 2. Task is breadth stage
        // 3. Estimated cost is within budget remaining
        let budget_allows = matches!(
            budget.sink_preference,
            crate::budget::expiry_policy::SinkPreference::FastMode
                | crate::budget::expiry_policy::SinkPreference::Auto
        );
        let stage_matches = task.stage == TaskStage::Breadth;
        let cost_ok = task.estimated_cost <= (budget.budget_limit - budget.spent_this_period);
        
        budget_allows && stage_matches && cost_ok
    }

    async fn absorb(&self, task: Task) -> anyhow::Result<SpendRecord> {
        let start = Utc::now();
        
        // Call Ollama API
        let url = format!("{}/api/generate", self.ollama_endpoint);
        let request = json!({
            "model": self.model,
            "prompt": task.payload["prompt"].as_str().unwrap_or(&task.description),
            "stream": false,
            "options": {
                "temperature": 0.7,
                "num_predict": 2048
            }
        });

        let response = self.http_client
            .post(&url)
            .json(&request)
            .send()
            .await?;

        let success = response.status().is_success();
        let error = if !success {
            Some(response.text().await.unwrap_or_default())
        } else {
            None
        };

        // Estimate cost: local compute is ~$0.0001 per 1k tokens
        // For simplicity, use a fixed small cost
        let amount = 0.001; // $0.001 per fast-mode task

        Ok(SpendRecord {
            id: Uuid::new_v4(),
            task_id: task.id,
            budget_id: task.budget_id,
            amount,
            model: self.model.clone(),
            mode: SinkMode::FastMode,
            timestamp: start,
            success,
            error,
        })
    }

    fn mode(&self) -> SinkMode {
        SinkMode::FastMode
    }

    fn name(&self) -> &'static str {
        "FastModeSink (Ollama/Gemma)"
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::budget::expiry_policy::{Budget, SinkPreference};
    use chrono::Utc;

    #[tokio::test]
    async fn test_fast_mode_sink_can_absorb() {
        let sink = FastModeSink::default_local();
        let budget = Budget {
            id: BudgetId::new(),
            name: "Test".to_string(),
            budget_limit: 10.0,
            spent_this_period: 0.0,
            period_start: Utc::now(),
            period_days: 30,
            expires_at: Some(Utc::now() + chrono::Duration::days(30)),
            minimum_spend_rate: 0.05,
            is_active: true,
            sink_preference: SinkPreference::Auto,
        };
        
        let task = Task {
            id: Uuid::new_v4(),
            budget_id: budget.id,
            description: "Research task".to_string(),
            stage: TaskStage::Breadth,
            estimated_cost: 0.01,
            payload: serde_json::json!({"prompt": "test"}),
            created_at: Utc::now(),
        };

        assert!(sink.can_absorb(&budget, &task));
        
        // Wrong stage
        let task_depth = Task { stage: TaskStage::Depth, ..task.clone() };
        assert!(!sink.can_absorb(&budget, &task_depth));
        
        // Budget prefers quality
        let budget_quality = Budget { sink_preference: SinkPreference::QualityMode, ..budget };
        assert!(!sink.can_absorb(&budget_quality, &task));
    }
}