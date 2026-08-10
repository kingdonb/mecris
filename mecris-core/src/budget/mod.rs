//! Budget governor module

pub mod budget_ledger;
pub mod expiry_policy;
pub mod fast_mode_sink;
pub mod governor_loop;
pub mod quality_mode_sink;
pub mod sink_registry;
pub mod twilio_watcher;

// Re-export main types
pub use budget_ledger::{BudgetLedger, TwilioProjection};
pub use expiry_policy::{Budget, BudgetId, ExpiryPolicy, SinkPreference};
pub use fast_mode_sink::FastModeSink;
pub use governor_loop::{GovernorConfig, GovernorLoop, LedgerTaskPicker, TaskPicker};
pub use quality_mode_sink::QualityModeSink;
pub use sink_registry::{Sink, SinkMode, SinkRegistry, SpendRecord, Task, TaskStage};
pub use twilio_watcher::{TwilioWatcher, TwilioWatcherConfig, budget_routes, handle_twilio_budget_get};