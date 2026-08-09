//! Budget ledger - SQLite persistence for budgets and spend records

use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use rusqlite::{params, Connection, OptionalExtension, Result};
use serde_json;
use std::path::Path;
use std::sync::Mutex;
use uuid::Uuid;

use crate::budget::expiry_policy::{Budget, BudgetId, ExpiryPolicy};
use crate::budget::sink_registry::{SpendRecord, Task};

/// Budget ledger using SQLite
pub struct BudgetLedger {
    conn: Mutex<Connection>,
}

impl BudgetLedger {
    /// Opens or creates the ledger database
    pub fn new<P: AsRef<Path>>(path: P) -> Result<Self> {
        let conn = Connection::open(path)?;
        let ledger = Self { conn: Mutex::new(conn) };
        ledger.init_schema()?;
        Ok(ledger)
    }

    /// Creates an in-memory ledger for testing
    pub fn new_in_memory() -> Result<Self> {
        let conn = Connection::open_in_memory()?;
        let ledger = Self { conn: Mutex::new(conn) };
        ledger.init_schema()?;
        Ok(ledger)
    }

    fn init_schema(&self) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute_batch(
            r#"
            CREATE TABLE IF NOT EXISTS budgets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                budget_limit REAL NOT NULL,
                spent_this_period REAL NOT NULL DEFAULT 0,
                period_start TEXT NOT NULL,
                period_days INTEGER NOT NULL,
                expires_at TEXT,
                minimum_spend_rate REAL NOT NULL DEFAULT 0.05,
                is_active INTEGER NOT NULL DEFAULT 1,
                sink_preference TEXT NOT NULL DEFAULT 'Auto'
            );

            CREATE TABLE IF NOT EXISTS spend_records (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                budget_id TEXT NOT NULL,
                amount REAL NOT NULL,
                model TEXT NOT NULL,
                mode TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                success INTEGER NOT NULL,
                error TEXT,
                FOREIGN KEY (budget_id) REFERENCES budgets(id)
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                budget_id TEXT NOT NULL,
                description TEXT NOT NULL,
                stage TEXT NOT NULL,
                estimated_cost REAL NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (budget_id) REFERENCES budgets(id)
            );

            CREATE TABLE IF NOT EXISTS expiry_policies (
                budget_id TEXT PRIMARY KEY,
                expires_at TEXT NOT NULL,
                minimum_spend_rate REAL NOT NULL DEFAULT 0.05,
                alert_threshold_days INTEGER NOT NULL DEFAULT 7,
                FOREIGN KEY (budget_id) REFERENCES budgets(id)
            );

            CREATE INDEX IF NOT EXISTS idx_spend_records_budget_id ON spend_records(budget_id);
            CREATE INDEX IF NOT EXISTS idx_spend_records_timestamp ON spend_records(timestamp);
            CREATE INDEX IF NOT EXISTS idx_tasks_budget_id ON tasks(budget_id);
            "#,
        )?;
        Ok(())
    }

    // ===== Budget operations =====

    /// Inserts or updates a budget
    pub fn upsert_budget(&self, budget: &Budget) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            r#"
            INSERT INTO budgets (id, name, budget_limit, spent_this_period, period_start, period_days, expires_at, minimum_spend_rate, is_active, sink_preference)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)
            ON CONFLICT(id) DO UPDATE SET
                name = ?2,
                budget_limit = ?3,
                spent_this_period = ?4,
                period_start = ?5,
                period_days = ?6,
                expires_at = ?7,
                minimum_spend_rate = ?8,
                is_active = ?9,
                sink_preference = ?10
            "#,
            params![
                budget.id.0.to_string(),
                budget.name,
                budget.budget_limit,
                budget.spent_this_period,
                budget.period_start.to_rfc3339(),
                budget.period_days as i64,
                budget.expires_at.map(|dt| dt.to_rfc3339()),
                budget.minimum_spend_rate,
                budget.is_active as i64,
                format!("{:?}", budget.sink_preference),
            ],
        )?;
        Ok(())
    }

    /// Gets a budget by ID
    pub fn get_budget(&self, id: BudgetId) -> Result<Option<Budget>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            r#"
            SELECT id, name, budget_limit, spent_this_period, period_start, period_days, expires_at, minimum_spend_rate, is_active, sink_preference
            FROM budgets WHERE id = ?1
            "#,
        )?;
        let budget = stmt.query_row(params![id.0.to_string()], |row| self.row_to_budget(row)).optional()?;
        Ok(budget)
    }

    /// Gets all active budgets
    pub fn get_active_budgets(&self) -> Result<Vec<Budget>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            r#"
            SELECT id, name, budget_limit, spent_this_period, period_start, period_days, expires_at, minimum_spend_rate, is_active, sink_preference
            FROM budgets WHERE is_active = 1
            "#,
        )?;
        let budgets = stmt.query_map(params![], |row| self.row_to_budget(row))?.collect::<Result<Vec<_>>>()?;
        Ok(budgets)
    }

    /// Gets budgets that are due for soaking (5/5 rule)
    pub fn get_due_budgets(&self, now: DateTime<Utc>) -> Result<Vec<Budget>> {
        let budgets = self.get_active_budgets()?;
        Ok(budgets.into_iter().filter(|b| b.is_due_for_soak(now)).collect())
    }

    /// Updates spent amount for a budget
    pub fn add_spent(&self, budget_id: BudgetId, amount: f64) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "UPDATE budgets SET spent_this_period = spent_this_period + ?1 WHERE id = ?2",
            params![amount, budget_id.0.to_string()],
        )?;
        Ok(())
    }

    fn row_to_budget(&self, row: &rusqlite::Row) -> Result<Budget> {
        let sink_pref_str: String = row.get(9)?;
        let sink_preference = match sink_pref_str.as_str() {
            "FastMode" => crate::budget::expiry_policy::SinkPreference::FastMode,
            "QualityMode" => crate::budget::expiry_policy::SinkPreference::QualityMode,
            _ => crate::budget::expiry_policy::SinkPreference::Auto,
        };

        Ok(Budget {
            id: BudgetId(Uuid::parse_str(&row.get::<_, String>(0)?).unwrap()),
            name: row.get(1)?,
            budget_limit: row.get(2)?,
            spent_this_period: row.get(3)?,
            period_start: DateTime::parse_from_rfc3339(&row.get::<_, String>(4)?).unwrap().with_timezone(&Utc),
            period_days: row.get::<_, i64>(5)? as u32,
            expires_at: row.get::<_, Option<String>>(6)?.map(|s| DateTime::parse_from_rfc3339(&s).unwrap().with_timezone(&Utc)),
            minimum_spend_rate: row.get(7)?,
            is_active: row.get::<_, i64>(8)? != 0,
            sink_preference,
        })
    }

    // ===== Spend record operations =====

    /// Records a spend event
    pub fn record_spend(&self, record: &SpendRecord) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            r#"
            INSERT INTO spend_records (id, task_id, budget_id, amount, model, mode, timestamp, success, error)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)
            "#,
            params![
                record.id.to_string(),
                record.task_id.to_string(),
                record.budget_id.0.to_string(),
                record.amount,
                record.model,
                format!("{:?}", record.mode),
                record.timestamp.to_rfc3339(),
                record.success as i64,
                record.error,
            ],
        )?;
        Ok(())
    }

    /// Gets spend records for a budget in a time range
    pub fn get_spend_records(&self, budget_id: BudgetId, since: DateTime<Utc>) -> Result<Vec<SpendRecord>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            r#"
            SELECT id, task_id, budget_id, amount, model, mode, timestamp, success, error
            FROM spend_records
            WHERE budget_id = ?1 AND timestamp >= ?2
            ORDER BY timestamp DESC
            "#,
        )?;
        let records = stmt.query_map(params![budget_id.0.to_string(), since.to_rfc3339()], |row| self.row_to_spend_record(row))?.collect::<Result<Vec<_>>>()?;
        Ok(records)
    }

    /// Gets total spent for a budget since a timestamp
    pub fn get_total_spent_since(&self, budget_id: BudgetId, since: DateTime<Utc>) -> Result<f64> {
        let conn = self.conn.lock().unwrap();
        let total: f64 = conn.query_row(
            "SELECT COALESCE(SUM(amount), 0) FROM spend_records WHERE budget_id = ?1 AND timestamp >= ?2 AND success = 1",
            params![budget_id.0.to_string(), since.to_rfc3339()],
            |row| row.get(0),
        )?;
        Ok(total)
    }

    fn row_to_spend_record(&self, row: &rusqlite::Row) -> Result<SpendRecord> {
        let mode_str: String = row.get(5)?;
        let mode = match mode_str.as_str() {
            "FastMode" => crate::budget::sink_registry::SinkMode::FastMode,
            _ => crate::budget::sink_registry::SinkMode::QualityMode,
        };

        Ok(SpendRecord {
            id: Uuid::parse_str(&row.get::<_, String>(0)?).unwrap(),
            task_id: Uuid::parse_str(&row.get::<_, String>(1)?).unwrap(),
            budget_id: BudgetId(Uuid::parse_str(&row.get::<_, String>(2)?).unwrap()),
            amount: row.get(3)?,
            model: row.get(4)?,
            mode,
            timestamp: DateTime::parse_from_rfc3339(&row.get::<_, String>(6)?).unwrap().with_timezone(&Utc),
            success: row.get::<_, i64>(7)? != 0,
            error: row.get(8)?,
        })
    }

    // ===== Task operations =====

    /// Adds a task to the backlog
    pub fn add_task(&self, task: &Task) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            r#"
            INSERT INTO tasks (id, budget_id, description, stage, estimated_cost, payload, created_at)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
            "#,
            params![
                task.id.to_string(),
                task.budget_id.0.to_string(),
                task.description,
                format!("{:?}", task.stage),
                task.estimated_cost,
                serde_json::to_string(&task.payload).unwrap(),
                task.created_at.to_rfc3339(),
            ],
        )?;
        Ok(())
    }

    /// Gets ready tasks for a budget (breadth first, then depth)
    pub fn get_ready_tasks(&self, budget_id: BudgetId, limit: usize) -> Result<Vec<Task>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            r#"
            SELECT id, budget_id, description, stage, estimated_cost, payload, created_at
            FROM tasks
            WHERE budget_id = ?1
            ORDER BY 
                CASE stage WHEN 'Breadth' THEN 0 ELSE 1 END,
                created_at ASC
            LIMIT ?2
            "#,
        )?;
        let tasks = stmt.query_map(params![budget_id.0.to_string(), limit as i64], |row| self.row_to_task(row))?.collect::<Result<Vec<_>>>()?;
        Ok(tasks)
    }

    fn row_to_task(&self, row: &rusqlite::Row) -> Result<Task> {
        let stage_str: String = row.get(3)?;
        let stage = match stage_str.as_str() {
            "Breadth" => crate::budget::sink_registry::TaskStage::Breadth,
            _ => crate::budget::sink_registry::TaskStage::Depth,
        };

        Ok(Task {
            id: Uuid::parse_str(&row.get::<_, String>(0)?).unwrap(),
            budget_id: BudgetId(Uuid::parse_str(&row.get::<_, String>(1)?).unwrap()),
            description: row.get(2)?,
            stage,
            estimated_cost: row.get(4)?,
            payload: serde_json::from_str(&row.get::<_, String>(5)?).unwrap_or_default(),
            created_at: DateTime::parse_from_rfc3339(&row.get::<_, String>(6)?).unwrap().with_timezone(&Utc),
        })
    }

    // ===== Expiry policy operations =====

    /// Upserts an expiry policy
    pub fn upsert_expiry_policy(&self, policy: &ExpiryPolicy) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            r#"
            INSERT INTO expiry_policies (budget_id, expires_at, minimum_spend_rate, alert_threshold_days)
            VALUES (?1, ?2, ?3, ?4)
            ON CONFLICT(budget_id) DO UPDATE SET
                expires_at = ?2,
                minimum_spend_rate = ?3,
                alert_threshold_days = ?4
            "#,
            params![
                policy.budget_id.0.to_string(),
                policy.expires_at.to_rfc3339(),
                policy.minimum_spend_rate,
                policy.alert_threshold_days as i64,
            ],
        )?;
        Ok(())
    }

    /// Gets expiry policy for a budget
    pub fn get_expiry_policy(&self, budget_id: BudgetId) -> Result<Option<ExpiryPolicy>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            "SELECT budget_id, expires_at, minimum_spend_rate, alert_threshold_days FROM expiry_policies WHERE budget_id = ?1"
        )?;
        let policy = stmt.query_row(params![budget_id.0.to_string()], |row| {
            Ok(ExpiryPolicy {
                budget_id: BudgetId(Uuid::parse_str(&row.get::<_, String>(0)?).unwrap()),
                expires_at: DateTime::parse_from_rfc3339(&row.get::<_, String>(1)?).unwrap().with_timezone(&Utc),
                minimum_spend_rate: row.get(2)?,
                alert_threshold_days: row.get::<_, i64>(3)? as u32,
            })
        }).optional()?;
        Ok(policy)
    }

    // ===== Twilio inventory =====

    /// Adds/updates Twilio balance (non-expiring budget)
    pub fn upsert_twilio_balance(&self, balance: f64, _monthly_burn: f64) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        let budget = Budget {
            id: BudgetId(Uuid::nil()), // Fixed ID for Twilio
            name: "Twilio".to_string(),
            budget_limit: 30.0,
            spent_this_period: 30.0 - balance,
            period_start: Utc::now(),
            period_days: 30,
            expires_at: None,
            minimum_spend_rate: 0.0,
            is_active: true,
            sink_preference: crate::budget::expiry_policy::SinkPreference::Auto,
        };
        self.upsert_budget(&budget)
    }

    /// Gets Twilio inventory projection
    pub fn get_twilio_projection(&self) -> Result<TwilioProjection> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            r#"SELECT id, name, budget_limit, spent_this_period, period_start, period_days, expires_at, minimum_spend_rate, is_active, sink_preference
            FROM budgets WHERE id = ?1"#
        )?;
        let budget = stmt.query_row(params![Uuid::nil().to_string()], |row| self.row_to_budget(row)).optional()?;
        match budget {
            Some(b) => {
                let balance = b.budget_limit - b.spent_this_period;
                let monthly_burn = 2.3; // Default estimate
                let projected_exhaustion = if b.spent_this_period > 0.0 && monthly_burn > 0.0 {
                    let months_remaining = balance / monthly_burn;
                    Some(Utc::now() + Duration::days((months_remaining * 30.0) as i64))
                } else {
                    None
                };
                Ok(TwilioProjection {
                    balance,
                    monthly_burn,
                    projected_exhaustion,
                })
            }
            None => Ok(TwilioProjection {
                balance: 0.0,
                monthly_burn: 0.0,
                projected_exhaustion: None,
            }),
        }
    }
}

/// Twilio inventory projection
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TwilioProjection {
    pub balance: f64,
    pub monthly_burn: f64,
    pub projected_exhaustion: Option<DateTime<Utc>>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::budget::expiry_policy::{Budget, SinkPreference};
    use chrono::Utc;

    #[test]
    fn test_ledger_budget_crud() {
        let ledger = BudgetLedger::new_in_memory().unwrap();
        let budget = Budget {
            id: BudgetId::new(),
            name: "Test Budget".to_string(),
            budget_limit: 100.0,
            spent_this_period: 10.0,
            period_start: Utc::now(),
            period_days: 30,
            expires_at: Some(Utc::now() + chrono::Duration::days(30)),
            minimum_spend_rate: 0.05,
            is_active: true,
            sink_preference: SinkPreference::Auto,
        };

        ledger.upsert_budget(&budget).unwrap();
        let retrieved = ledger.get_budget(budget.id).unwrap().unwrap();
        assert_eq!(retrieved.name, "Test Budget");
        assert_eq!(retrieved.budget_limit, 100.0);
    }

    #[test]
    fn test_ledger_spend_recording() {
        let ledger = BudgetLedger::new_in_memory().unwrap();
        let budget = Budget {
            id: BudgetId::new(),
            name: "Test".to_string(),
            budget_limit: 100.0,
            spent_this_period: 0.0,
            period_start: Utc::now(),
            period_days: 30,
            expires_at: Some(Utc::now() + chrono::Duration::days(30)),
            minimum_spend_rate: 0.05,
            is_active: true,
            sink_preference: SinkPreference::Auto,
        };
        ledger.upsert_budget(&budget).unwrap();

        let record = crate::budget::sink_registry::SpendRecord {
            id: Uuid::new_v4(),
            task_id: Uuid::new_v4(),
            budget_id: budget.id,
            amount: 0.50,
            model: "gemma:2b".to_string(),
            mode: crate::budget::sink_registry::SinkMode::FastMode,
            timestamp: Utc::now(),
            success: true,
            error: None,
        };
        ledger.record_spend(&record).unwrap();
        ledger.add_spent(budget.id, 0.50).unwrap();

        let retrieved = ledger.get_budget(budget.id).unwrap().unwrap();
        assert_eq!(retrieved.spent_this_period, 0.50);
    }
}