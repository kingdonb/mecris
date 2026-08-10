//! Budget types and expiry policy

use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Unique identifier for a budget
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct BudgetId(pub Uuid);

impl BudgetId {
    pub fn new() -> Self {
        Self(Uuid::new_v4())
    }
}

impl Default for BudgetId {
    fn default() -> Self {
        Self::new()
    }
}

/// Budget configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Budget {
    pub id: BudgetId,
    pub name: String,
    pub budget_limit: f64,  // Total budget per period (e.g., $100/month)              // Total budget per period (e.g., $100/month)
    pub spent_this_period: f64,  // Amount spent in current period
    pub period_start: DateTime<Utc>,
    pub period_days: u32,        // Billing period in days
    pub expires_at: Option<DateTime<Utc>>,  // None = non-expiring
    pub minimum_spend_rate: f64, // 0.05 = 5% (the "5/5" guarantee)
    pub is_active: bool,
    pub sink_preference: SinkPreference,
}

impl Budget {
    /// Returns the fraction of budget spent this period (0.0 to 1.0+)
    pub fn spend_fraction(&self) -> f64 {
        if self.budget_limit <= 0.0 {
            0.0
        } else {
            self.spent_this_period / self.budget_limit
        }
    }

    /// Returns the fraction of the billing period elapsed (0.0 to 1.0+)
    pub fn period_elapsed_fraction(&self, now: DateTime<Utc>) -> f64 {
        let period_duration = Duration::days(self.period_days as i64);
        let elapsed = now - self.period_start;
        if elapsed <= Duration::zero() {
            0.0
        } else {
            elapsed.num_milliseconds() as f64 / period_duration.num_milliseconds() as f64
        }
    }

    /// Returns true if this budget is expiring (has an expiry date)
    pub fn is_expiring(&self) -> bool {
        self.expires_at.is_some()
    }

    /// Returns true if the budget is due for soaking (under 5/5 threshold)
    pub fn is_due_for_soak(&self, now: DateTime<Utc>) -> bool {
        if !self.is_active {
            return false;
        }
        if !self.is_expiring() {
            return false; // Non-expiring budgets are ignored by governor
        }
        if let Some(expires) = self.expires_at {
            if now >= expires {
                return false; // Already expired
            }
        }
        // 5/5 rule: spent < 5% AND period_elapsed < 5%
        self.spend_fraction() < self.minimum_spend_rate
            && self.period_elapsed_fraction(now) < self.minimum_spend_rate
    }

    /// Minimum amount that should be spent to satisfy 5/5
    pub fn minimum_spend_target(&self) -> f64 {
        self.budget_limit * self.minimum_spend_rate
    }

    /// Amount still needed to reach 5/5 threshold
    pub fn soak_deficit(&self) -> f64 {
        (self.minimum_spend_target() - self.spent_this_period).max(0.0)
    }
}

/// Preference for which sink to use
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SinkPreference {
    FastMode,    // Local Gemma/Ollama for breadth
    QualityMode, // Cloud Sonnet/Opus for depth
    Auto,        // Governor decides based on task stage
}

/// Expiry policy for a budget
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExpiryPolicy {
    pub budget_id: BudgetId,
    pub expires_at: DateTime<Utc>,
    pub minimum_spend_rate: f64, // Default 0.05 (5%)
    pub alert_threshold_days: u32, // Days before expiry to alert
}

impl ExpiryPolicy {
    pub fn new(budget_id: BudgetId, expires_at: DateTime<Utc>) -> Self {
        Self {
            budget_id,
            expires_at,
            minimum_spend_rate: 0.05,
            alert_threshold_days: 7,
        }
    }

    /// Checks if the budget is in the alert window
    pub fn is_in_alert_window(&self, now: DateTime<Utc>) -> bool {
        let alert_start = self.expires_at - Duration::days(self.alert_threshold_days as i64);
        now >= alert_start && now < self.expires_at
    }

    /// Days until expiry
    pub fn days_until_expiry(&self, now: DateTime<Utc>) -> i64 {
        (self.expires_at - now).num_days().max(0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    #[test]
    fn test_budget_spend_fraction() {
        let budget = Budget {
            id: BudgetId::new(),
            name: "Test".to_string(),
            budget_limit: 100.0,
            spent_this_period: 25.0,
            period_start: Utc::now(),
            period_days: 30,
            expires_at: None,
            minimum_spend_rate: 0.05,
            is_active: true,
            sink_preference: SinkPreference::Auto,
        };
        assert_eq!(budget.spend_fraction(), 0.25);
    }

    #[test]
    fn test_budget_is_due_for_soak() {
        let now = Utc::now();
        let period_start = now - Duration::hours(12); // 5% of 30 days = 36 hours, so 12h < 5%
        
        let budget = Budget {
            id: BudgetId::new(),
            name: "Expiring".to_string(),
            budget_limit: 100.0,
            spent_this_period: 1.0, // 1% spent
            period_start,
            period_days: 30,
            expires_at: Some(now + Duration::days(30)),
            minimum_spend_rate: 0.05,
            is_active: true,
            sink_preference: SinkPreference::Auto,
        };
        
        assert!(budget.is_due_for_soak(now));
        
        // Not due if already spent 5%
        let budget_spent = Budget { spent_this_period: 5.0, ..budget.clone() };
        assert!(!budget_spent.is_due_for_soak(now));
        
        // Not due if non-expiring
        let budget_non_expiring = Budget { expires_at: None, ..budget.clone() };
        assert!(!budget_non_expiring.is_due_for_soak(now));
    }

    #[test]
    fn test_expiry_policy_alert_window() {
        let now = Utc::now();
        let policy = ExpiryPolicy::new(BudgetId::new(), now + Duration::days(5));
        
        assert!(policy.is_in_alert_window(now));
        assert_eq!(policy.days_until_expiry(now), 5);
    }
}