//! ReviewPump — daily language review target calculator.
//!
//! Pure arithmetic, zero host dependencies.  Ported from `services/review_pump.py`.
//!
//! # Multiplier encoding
//! Multipliers are stored as integer tenths to avoid IEEE 754 comparison hazards
//! in the static lever config table:
//!   10 → 1.0x (Maintenance)
//!   20 → 2.0x (Steady)
//!  100 → 10.0x (System Overdrive)

use serde::{Deserialize, Serialize};

/// Max points awarded per correctly answered Arabic hard card.
/// Using the max (16) rather than the average ((8+16)/2=12) prevents
/// the Nag Engine from prematurely marking the Arabic goal "done"
/// when only easy/new cards were played (kingdonb/mecris#151).
pub const ARABIC_POINTS_PER_CARD: i32 = 16;

/// One row in the lever configuration table.
#[derive(Debug, Clone)]
struct LeverConfig {
    name: &'static str,
    /// Clearance window in days. `None` = Maintenance mode (no backlog clearing).
    days: Option<u32>,
}

/// Static lever config table. Key = multiplier × 10 (integer tenths).
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

/// Calculate the daily target completions.
///
/// Formula: `tomorrow_liability + (current_debt / clearance_days)`
///
/// In Maintenance mode (`days = None`), target equals `tomorrow_liability` (no debt clearing).
pub fn calculate_target(debt: i32, tomorrow_liability: i32, multiplier_x10: u32) -> i32 {
    let config = lookup(multiplier_x10);
    match config.days {
        None => tomorrow_liability,
        Some(days) => tomorrow_liability + (debt / days as i32),
    }
}

/// Full pump status, mirroring the Python `get_status` return dict.
#[derive(Debug, Serialize, Deserialize)]
pub struct PumpStatus {
    pub multiplier_x10: u32,
    pub lever_name: String,
    pub target_flow_rate: i32,
    pub current_flow_rate: i32,
    /// "cavitation" | "laminar" | "turbulent"
    pub status: String,
    pub debt_remaining: i32,
    pub unit: String,
}

/// Return full pump status including flow state classification.
///
/// Flow states:
/// - `cavitation`:  daily_completions < tomorrow_liability  (falling behind baseline)
/// - `turbulent`:   daily_completions >= target AND target > 0  (ahead of schedule)
/// - `laminar`:     otherwise  (normal healthy flow)
pub fn get_status(
    debt: i32,
    tomorrow_liability: i32,
    daily_completions: i32,
    multiplier_x10: u32,
    unit: &str,
) -> PumpStatus {
    let config = lookup(multiplier_x10);
    let target = calculate_target(debt, tomorrow_liability, multiplier_x10);

    let status = if daily_completions < tomorrow_liability {
        "cavitation"
    } else if target > 0 && daily_completions >= target {
        "turbulent"
    } else {
        "laminar"
    };

    PumpStatus {
        multiplier_x10,
        lever_name: config.name.to_string(),
        target_flow_rate: target,
        current_flow_rate: daily_completions,
        status: status.to_string(),
        debt_remaining: debt,
        unit: unit.to_string(),
    }
}

/// Request body for the HTTP endpoint.
#[derive(Deserialize)]
pub struct PumpRequest {
    pub debt: i32,
    pub tomorrow_liability: i32,
    pub daily_completions: i32,
    pub multiplier_x10: u32,
    #[serde(default = "default_unit")]
    pub unit: String,
}

fn default_unit() -> String {
    "points".to_string()
}

// ---------------------------------------------------------------------------
// Spin HTTP handler — compiled only when the "spin" feature is enabled.
// ---------------------------------------------------------------------------
#[cfg(feature = "spin")]
mod spin_handler {
    use super::*;
    use spin_sdk::http::{IntoResponse, Request, Response};
    use spin_sdk::http_component;

    #[http_component]
    fn handle_review_pump(req: Request) -> anyhow::Result<impl IntoResponse> {
        let body = req.body();
        let pr: PumpRequest = serde_json::from_slice(body).unwrap_or_else(|_| PumpRequest {
            debt: 0,
            tomorrow_liability: 0,
            daily_completions: 0,
            multiplier_x10: 10,
            unit: "points".to_string(),
        });

        let status = get_status(
            pr.debt,
            pr.tomorrow_liability,
            pr.daily_completions,
            pr.multiplier_x10,
            &pr.unit,
        );

        let json = serde_json::to_string(&status)?;
        Ok(Response::builder()
            .status(200)
            .header("content-type", "application/json")
            .body(json)
            .build())
    }
}

// ---------------------------------------------------------------------------
// Unit tests
// ---------------------------------------------------------------------------
#[cfg(test)]
mod tests {
    use super::*;

    // --- calculate_target ---

    #[test]
    fn maintenance_returns_liability_only() {
        // multiplier_x10=10 → Maintenance → days=None → target = tomorrow_liability
        assert_eq!(calculate_target(1000, 50, 10), 50);
    }

    #[test]
    fn steady_clears_debt_over_14_days() {
        // 2.0x Steady: target = liability + debt/14
        assert_eq!(calculate_target(140, 50, 20), 50 + 140 / 14); // 60
    }

    #[test]
    fn brisk_clears_debt_over_10_days() {
        assert_eq!(calculate_target(100, 50, 30), 50 + 100 / 10); // 60
    }

    #[test]
    fn aggressive_clears_debt_over_7_days() {
        assert_eq!(calculate_target(70, 50, 40), 50 + 70 / 7); // 60
    }

    #[test]
    fn high_pressure_clears_debt_over_5_days() {
        assert_eq!(calculate_target(50, 50, 50), 50 + 50 / 5); // 60
    }

    #[test]
    fn very_high_clears_debt_over_3_days() {
        assert_eq!(calculate_target(30, 50, 60), 50 + 30 / 3); // 60
    }

    #[test]
    fn the_blitz_clears_debt_over_2_days() {
        assert_eq!(calculate_target(20, 50, 70), 50 + 20 / 2); // 60
    }

    #[test]
    fn system_overdrive_clears_debt_over_1_day() {
        assert_eq!(calculate_target(10, 50, 100), 50 + 10 / 1); // 60
    }

    #[test]
    fn unknown_multiplier_falls_back_to_maintenance() {
        // 999 is not a valid key → falls back to Maintenance (days=None)
        assert_eq!(calculate_target(1000, 50, 999), 50);
    }

    #[test]
    fn zero_debt_any_multiplier() {
        // No backlog → target = tomorrow_liability for all levers
        for &(m, _) in LEVER_CONFIG {
            assert_eq!(calculate_target(0, 100, m), 100, "failed for multiplier_x10={}", m);
        }
    }

    // --- get_status: flow states ---

    #[test]
    fn flow_state_cavitation_when_below_liability() {
        // daily_completions < tomorrow_liability → cavitation
        let s = get_status(0, 100, 50, 10, "points");
        assert_eq!(s.status, "cavitation");
    }

    #[test]
    fn flow_state_turbulent_when_at_or_above_target() {
        // 2.0x Steady: target = 50 + 140/14 = 60
        // daily_completions = 60 → turbulent
        let s = get_status(140, 50, 60, 20, "points");
        assert_eq!(s.status, "turbulent");
        assert_eq!(s.target_flow_rate, 60);
    }

    #[test]
    fn flow_state_laminar_between_liability_and_target() {
        // target = 60 (see steady test), completions = 55 → laminar
        let s = get_status(140, 50, 55, 20, "points");
        assert_eq!(s.status, "laminar");
    }

    #[test]
    fn flow_state_laminar_at_liability() {
        // daily_completions == tomorrow_liability (not < it) → not cavitation
        // target > daily_completions → not turbulent
        let s = get_status(140, 50, 50, 20, "points");
        assert_eq!(s.status, "laminar");
    }

    // --- get_status: metadata ---

    #[test]
    fn lever_name_matches_config() {
        let s = get_status(0, 100, 100, 40, "cards");
        assert_eq!(s.lever_name, "Aggressive");
        assert_eq!(s.unit, "cards");
        assert_eq!(s.multiplier_x10, 40);
    }

    #[test]
    fn arabic_points_per_card_constant() {
        assert_eq!(ARABIC_POINTS_PER_CARD, 16);
    }

    // --- turbulent-edge: target=0 should not trigger turbulent on 0 completions ---
    #[test]
    fn turbulent_not_triggered_when_target_is_zero() {
        // 1.0x Maintenance, liability=0, debt=0 → target=0; completions=0
        // Python: `elif daily_completions >= target and target > 0` — target > 0 guard
        let s = get_status(0, 0, 0, 10, "points");
        assert_eq!(s.status, "laminar");
    }
}
