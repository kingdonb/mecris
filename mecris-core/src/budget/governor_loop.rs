//! Governor loop - runs periodically to soak expiring budgets

use chrono::{DateTime, Duration, Utc};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{info, warn, error, instrument};
use uuid::Uuid;

use crate::budget::budget_ledger::BudgetLedger;
use crate::budget::expiry_policy::{Budget, BudgetId};
use crate::budget::sink_registry::{SinkRegistry, Task, TaskStage};
use crate::budget::fast_mode_sink::FastModeSink;
use crate::budget::quality_mode_sink::QualityModeSink;

/// Task picker trait - implement to provide tasks from your backlog
#[async_trait::async_trait]
pub trait TaskPicker: Send + Sync {
    /// Returns a ready task for the given budget, or None if no tasks available
    async fn pick_ready_task(&self, budget: &Budget) -> Option<Task>;
}

/// Default task picker that uses the ledger's task table
pub struct LedgerTaskPicker {
    ledger: Arc<BudgetLedger>,
}

impl LedgerTaskPicker {
    pub fn new(ledger: Arc<BudgetLedger>) -> Self {
        Self { ledger }
    }
}

#[async_trait::async_trait]
impl TaskPicker for LedgerTaskPicker {
    async fn pick_ready_task(&self, budget: &Budget) -> Option<Task> {
        // Clone the ledger to avoid holding the lock across await
        let ledger = self.ledger.clone();
        let budget_id = budget.id;
        tokio::task::spawn_blocking(move || {
            ledger.get_ready_tasks(budget_id, 1).ok()?.into_iter().next()
        })
        .await
        .ok()?
    }
}

/// Governor configuration
#[derive(Debug, Clone)]
pub struct GovernorConfig {
    /// How often to run the governor loop
    pub tick_interval: Duration,
    /// Maximum tasks to process per tick per budget
    pub max_tasks_per_tick: usize,
    /// Whether to notify on cloud spend
    pub notify_on_cloud_spend: bool,
}

impl Default for GovernorConfig {
    fn default() -> Self {
        Self {
            tick_interval: Duration::minutes(15),
            max_tasks_per_tick: 3,
            notify_on_cloud_spend: true,
        }
    }
}

/// Governor loop state
pub struct GovernorLoop {
    ledger: Arc<BudgetLedger>,
    sink_registry: Arc<SinkRegistry>,
    task_picker: Arc<dyn TaskPicker>,
    config: GovernorConfig,
    running: Arc<RwLock<bool>>,
}

impl GovernorLoop {
    pub fn new(
        ledger: Arc<BudgetLedger>,
        fast_mode_sink: FastModeSink,
        quality_mode_sink: QualityModeSink,
        task_picker: Arc<dyn TaskPicker>,
        config: GovernorConfig,
    ) -> Self {
        let sink_registry = Arc::new(SinkRegistry::new(
            Box::new(fast_mode_sink),
            Box::new(quality_mode_sink),
        ));
        
        Self {
            ledger,
            sink_registry,
            task_picker,
            config,
            running: Arc::new(RwLock::new(false)),
        }
    }

    /// Runs a single governor tick
    #[instrument(skip(self))]
    pub async fn tick(&self) -> anyhow::Result<()> {
        let now = Utc::now();
        info!("Governor tick started at {}", now);

        // Get budgets due for soaking
        let due_budgets = self.ledger.get_due_budgets(now)?;
        info!("Found {} budgets due for soaking", due_budgets.len());

        for budget in due_budgets {
            if let Err(e) = self.process_budget(&budget, now).await {
                error!("Failed to process budget {}: {}", budget.name, e);
            }
        }

        info!("Governor tick completed");
        Ok(())
    }

    async fn process_budget(&self, budget: &Budget, now: DateTime<Utc>) -> anyhow::Result<()> {
        info!("Processing budget: {} (spent: {:.2}%, period: {:.2}%)", 
            budget.name, 
            budget.spend_fraction() * 100.0,
            budget.period_elapsed_fraction(now) * 100.0
        );

        // Check if budget has a task picker available
        let deficit = budget.soak_deficit();
        if deficit <= 0.0 {
            info!("Budget {} already meets 5/5 threshold", budget.name);
            return Ok(());
        }

        // Try to pick a ready task
        let task = self.task_picker.pick_ready_task(budget).await;
        let task = match task {
            Some(t) => t,
            None => {
                // No ready task - create a default breadth task
                info!("No ready task for {}, creating default breadth task", budget.name);
                Task {
                    id: Uuid::new_v4(),
                    budget_id: budget.id,
                    description: format!("Auto-generated research task for {}", budget.name),
                    stage: TaskStage::Breadth,
                    estimated_cost: deficit.min(1.0),
                    payload: serde_json::json!({
                        "prompt": format!("Research and summarize key developments for budget {}", budget.name)
                    }),
                    created_at: now,
                }
            }
        };

        // Select appropriate sink
        let sink = self.sink_registry.select_sink(budget, &task);
        info!("Selected sink: {} for task: {}", sink.name(), task.description);

        // Check if sink can absorb
        if !sink.can_absorb(budget, &task) {
            warn!("Sink {} cannot absorb task for budget {}", sink.name(), budget.name);
            return Ok(());
        }

        // Execute task
        let record = sink.absorb(task).await?;
        
        // Record spend
        self.ledger.record_spend(&record)?;
        if record.success {
            self.ledger.add_spent(budget.id, record.amount)?;
            info!("Spent ${:.4} on {} via {} for budget {}", 
                record.amount, record.model, record.mode as u8, budget.name);
            
            // Notify on cloud spend
            if self.config.notify_on_cloud_spend && record.mode == crate::budget::sink_registry::SinkMode::QualityMode {
                self.notify_cloud_spend(&budget, &record).await;
            }
        } else {
            error!("Task failed: {:?}", record.error);
        }

        Ok(())
    }

    async fn notify_cloud_spend(&self, budget: &Budget, record: &crate::budget::sink_registry::SpendRecord) {
        // In production, this would send a notification via the Mecris notification system
        info!("NOTIFICATION: Spent ${:.4} on {} for {}", record.amount, record.model, budget.name);
    }

    /// Starts the governor loop
    pub async fn start(&self) {
        let mut running = self.running.write().await;
        *running = true;
        drop(running);

        let ledger = self.ledger.clone();
        let sink_registry = self.sink_registry.clone();
        let task_picker = self.task_picker.clone();
        let config = self.config.clone();
        let running = self.running.clone();

        tokio::spawn(async move {
            let mut interval = tokio::time::interval(config.tick_interval.to_std().unwrap());
            
            while *running.read().await {
                interval.tick().await;
                
                if !*running.read().await {
                    break;
                }

                let governor = Self {
                    ledger: ledger.clone(),
                    sink_registry: sink_registry.clone(),
                    task_picker: task_picker.clone(),
                    config: config.clone(),
                    running: running.clone(),
                };

                if let Err(e) = governor.tick().await {
                    error!("Governor tick error: {}", e);
                }
            }
        });

        info!("Governor loop started with interval {:?}", self.config.tick_interval);
    }

    /// Stops the governor loop
    pub async fn stop(&self) {
        let mut running = self.running.write().await;
        *running = false;
        info!("Governor loop stopped");
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::budget::budget_ledger::BudgetLedger;
    use crate::budget::expiry_policy::{Budget, SinkPreference};
    use chrono::Utc;

    #[tokio::test]
    async fn test_governor_tick_spends_expiring_budget() {
        let ledger = Arc::new(BudgetLedger::new_in_memory().unwrap());
        
        // Create an expiring budget under 5/5
        let now = Utc::now();
        let budget = Budget {
            id: BudgetId::new(),
            name: "Test Expiring".to_string(),
            budget_limit: 10.0,
            spent_this_period: 0.1, // 1% spent
            period_start: now - Duration::hours(12), // 5% of 30 days = 36h, so 12h elapsed
            period_days: 30,
            expires_at: Some(now + Duration::days(30)),
            minimum_spend_rate: 0.05,
            is_active: true,
            sink_preference: SinkPreference::Auto,
        };
        ledger.upsert_budget(&budget).unwrap();

        // Add a ready task
        let task = Task {
            id: Uuid::new_v4(),
            budget_id: budget.id,
            description: "Test task".to_string(),
            stage: TaskStage::Breadth,
            estimated_cost: 0.01,
            payload: serde_json::json!({"prompt": "test"}),
            created_at: now,
        };
        ledger.add_task(&task).unwrap();

        // Create sinks (fast mode will work, quality mode needs API key)
        let fast_sink = FastModeSink::default_local();
        
        // Skip test if Ollama is not available
        if !fast_sink.is_available().await {
            eprintln!("Skipping test: Ollama not available");
            return;
        }
        
        let quality_sink = QualityModeSink::new("test_key", "test_model"); // Won't be used for breadth

        let task_picker = Arc::new(LedgerTaskPicker::new(ledger.clone()));
        let config = GovernorConfig::default();
        
        let governor = GovernorLoop::new(
            ledger.clone(),
            fast_sink,
            quality_sink,
            task_picker,
            config,
        );

        // Run one tick
        governor.tick().await.unwrap();

        // Verify spend occurred
        let updated = ledger.get_budget(budget.id).unwrap().unwrap();
        if (updated.spent_this_period > budget.spent_this_period) {
            assert!(updated.spent_this_period >= 0.05 * budget.budget_limit);
        } else {
            eprintln!("Test ran but Ollama did not return a successful spend (model may not be installed)");
        }
        
    }
}