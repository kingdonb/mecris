uniffi::setup_scaffolding!();

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, uniffi::Record)]
pub struct PumpStatus {
    pub multiplier_x10: u32,
    pub lever_name: String,
    pub target_flow_rate: i32,
    pub current_flow_rate: i32,
    pub goal_met: bool,
    pub status: String,
    pub debt_remaining: i32,
    pub unit: String,
}

#[derive(Debug, Clone)]
struct LeverConfig {
    name: &'static str,
    days: Option<u32>,
}

const LEVER_CONFIG: &[(u32, LeverConfig)] = &[
    (10, LeverConfig { name: "Maintenance",    days: None     }),
    (20, LeverConfig { name: "Steady",         days: Some(14) }),
    (30, LeverConfig { name: "Brisk",          days: Some(10) }),
    (40, LeverConfig { name: "Aggressive",     days: Some(7)  }),
    (50, LeverConfig { name: "High Pressure",  days: Some(5)  }),
    (60, LeverConfig { name: "Very High",      days: Some(3)  }),
    (70, LeverConfig { name: "The Blitz",      days: Some(2)  }),
    (100, LeverConfig { name: "System Overdrive", days: Some(1) }),
];

fn lookup(multiplier_x10: u32) -> &'static LeverConfig {
    LEVER_CONFIG
        .iter()
        .find(|(k, _)| *k == multiplier_x10)
        .map(|(_, v)| v)
        .unwrap_or(&LEVER_CONFIG[0].1) // default: Maintenance
}

#[uniffi::export]
pub fn calculate_target(debt: i32, tomorrow_liability: i32, multiplier_x10: u32) -> i32 {
    let config = lookup(multiplier_x10);
    match config.days {
        None => tomorrow_liability,
        Some(days) => tomorrow_liability + (debt / days as i32),
    }
}

#[uniffi::export]
pub fn get_pump_status(
    debt: i32,
    tomorrow_liability: i32,
    daily_completions: i32,
    multiplier_x10: u32,
    unit: String,
) -> PumpStatus {
    let config = lookup(multiplier_x10);
    let mut target = calculate_target(debt, tomorrow_liability, multiplier_x10);

    let mut status = "laminar";
    let goal_met;

    if debt == 0 && tomorrow_liability == 0 {
        target = 0;
        status = "laminar";
        goal_met = true;
    } else {
        if daily_completions < tomorrow_liability {
            status = "cavitation";
        } else if target > 0 && daily_completions >= target {
            status = "turbulent";
        }
        goal_met = if target > 0 || (debt > 0 && multiplier_x10 > 10) { 
            daily_completions >= target 
        } else { 
            debt == 0 
        };
    }

    PumpStatus {
        multiplier_x10,
        lever_name: config.name.to_string(),
        target_flow_rate: (target - daily_completions).max(0),
        current_flow_rate: daily_completions,
        goal_met,
        status: status.to_string(),
        debt_remaining: debt,
        unit,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_maintenance_mode() {
        let status = get_pump_status(1000, 50, 50, 10, "points".to_string());
        assert_eq!(status.lever_name, "Maintenance");
        assert_eq!(status.target_flow_rate, 0); // completions=50, target=50
        assert_eq!(status.goal_met, true);
    }

    #[test]
    fn test_steady_mode_debt() {
        // target = 50 + 140/14 = 60
        let status = get_pump_status(140, 50, 50, 20, "points".to_string());
        assert_eq!(status.lever_name, "Steady");
        assert_eq!(status.target_flow_rate, 10); // target=60, completions=50
        assert_eq!(status.goal_met, false);
    }

    #[test]
    fn test_cavitation_state() {
        // daily_completions (40) < tomorrow_liability (50) → cavitation
        let status = get_pump_status(100, 50, 40, 10, "points".to_string());
        assert_eq!(status.status, "cavitation");
        assert_eq!(status.goal_met, false);
    }

    #[test]
    fn test_system_overdrive_blitz() {
        // 10.0x Overdrive: clears all debt in 1 day
        // target = 50 + 100/1 = 150
        let status = get_pump_status(100, 50, 150, 100, "points".to_string());
        assert_eq!(status.lever_name, "System Overdrive");
        assert_eq!(status.status, "turbulent");
        assert_eq!(status.goal_met, true);
    }
}
