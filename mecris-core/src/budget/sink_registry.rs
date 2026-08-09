//! Sink registry and trait definitions

use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::budget::expiry_policy::{Budget, BudgetId, SinkPreference};

/// A task that can be executed by a sink
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Task {
    pub id: Uuid,
    pub budget_id: BudgetId,
    pub description: String,
    pub stage: TaskStage,
    pub estimated_cost: f64,
    pub payload: serde_json::Value,
    pub created_at: DateTime<Utc>,
}

/// Stage of the task (breadth vs depth)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TaskStage {
    Breadth,  // Research, exploration - fast mode
    Depth,    // Final review, commit - quality mode
}

/// Result of a sink executing a task
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpendRecord {
    pub id: Uuid,
    pub task_id: Uuid,
    pub budget_id: BudgetId,
    pub amount: f64,
    pub model: String,
    pub mode: SinkMode,
    pub timestamp: DateTime<Utc>,
    pub success: bool,
    pub error: Option<String>,
}

/// Mode of the sink that executed the task
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SinkMode {
    FastMode,
    QualityMode,
}

/// Trait for budget sinks
#[async_trait]
pub trait Sink: Send + Sync {
    /// Returns true if this sink can absorb the given budget's task
    fn can_absorb(&self, budget: &Budget, task: &Task) -> bool;

    /// Executes the task and returns a spend record
    async fn absorb(&self, task: Task) -> anyhow::Result<SpendRecord>;

    /// Returns the sink mode
    fn mode(&self) -> SinkMode;

    /// Returns the sink name for logging
    fn name(&self) -> &'static str;
}

/// Sink registry - manages all available sinks
pub struct SinkRegistry {
    fast_mode_sink: Box<dyn Sink>,
    quality_mode_sink: Box<dyn Sink>,
}

impl SinkRegistry {
    pub fn new(
        fast_mode_sink: Box<dyn Sink>,
        quality_mode_sink: Box<dyn Sink>,
    ) -> Self {
        Self {
            fast_mode_sink,
            quality_mode_sink,
        }
    }

    /// Selects the appropriate sink for a task
    pub fn select_sink(&self, budget: &Budget, task: &Task) -> &dyn Sink {
        match budget.sink_preference {
            SinkPreference::FastMode => self.fast_mode_sink.as_ref(),
            SinkPreference::QualityMode => self.quality_mode_sink.as_ref(),
            SinkPreference::Auto => {
                if task.stage == TaskStage::Breadth {
                    self.fast_mode_sink.as_ref()
                } else {
                    self.quality_mode_sink.as_ref()
                }
            }
        }
    }

    /// Gets the fast mode sink
    pub fn fast_mode(&self) -> &dyn Sink {
        self.fast_mode_sink.as_ref()
    }

    /// Gets the quality mode sink
    pub fn quality_mode(&self) -> &dyn Sink {
        self.quality_mode_sink.as_ref()
    }
}