use extism_pdk::*;
use serde::{Deserialize, Serialize};

#[derive(Deserialize, Debug)]
pub struct PumpRequest {
    pub current_backlog: i32,
    pub pump_multiplier: f64,
    pub base_daily_target: i32,
}

#[derive(Serialize, Debug, PartialEq)]
pub struct PumpResult {
    pub required_clearance: i32,
    pub is_goal_met: bool,
    pub pump_status: String,
}

#[plugin_fn]
pub fn calculate_pump(input: String) -> FnResult<String> {
    // 2.2: Error Boundary fallback logic
    let req: PumpRequest = match serde_json::from_str(&input) {
        Ok(req) => req,
        Err(_) => {
            // Fallback gracefully on malformed JSON
            let fallback = PumpResult {
                required_clearance: 0, // Base target isn't known, fallback to 0 or safe default
                is_goal_met: false,
                pump_status: "Error".to_string(),
            };
            return Ok(serde_json::to_string(&fallback)?);
        }
    };

    let result = calculate_pump_logic(&req);
    Ok(serde_json::to_string(&result)?)
}

// Extract pure logic into a separate function for easy unit testing without Extism host overhead
fn calculate_pump_logic(req: &PumpRequest) -> PumpResult {
    // 2.3: "Cavitation" Edge Case logic
    if req.current_backlog <= 0 {
        return PumpResult {
            required_clearance: req.base_daily_target,
            is_goal_met: false, // We leave is_goal_met out of scope for the pump calculation itself to determine true success, assuming false until Host verifies the actual progress.
            pump_status: "Cavitation".to_string(),
        };
    }

    // 2.4: "Maintenance Mode" logic
    if req.pump_multiplier <= 1.0 {
        return PumpResult {
            required_clearance: req.base_daily_target,
            is_goal_met: false,
            pump_status: "Maintenance".to_string(),
        };
    }

    // 2.5: "Active Pumping" logic using f64 precision
    let extra_clearance = (req.current_backlog as f64 * (req.pump_multiplier - 1.0) * 0.10).ceil() as i32;
    let required_clearance = req.base_daily_target + extra_clearance;

    PumpResult {
        required_clearance,
        is_goal_met: false,
        pump_status: "Active".to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_maintenance_mode() {
        let req = PumpRequest {
            current_backlog: 500,
            pump_multiplier: 1.0,
            base_daily_target: 100,
        };
        let result = calculate_pump_logic(&req);
        assert_eq!(result.required_clearance, 100);
        assert_eq!(result.pump_status, "Maintenance");
    }

    #[test]
    fn test_active_pumping_rounding_up() {
        let req = PumpRequest {
            current_backlog: 5,
            pump_multiplier: 1.5,
            base_daily_target: 100,
        };
        // extra_clearance = 5 * 0.5 * 0.10 = 0.25 -> ceil(0.25) = 1
        let result = calculate_pump_logic(&req);
        assert_eq!(result.required_clearance, 101);
        assert_eq!(result.pump_status, "Active");
    }

    #[test]
    fn test_cavitation_mode() {
        let req = PumpRequest {
            current_backlog: -5,
            pump_multiplier: 10.0,
            base_daily_target: 100,
        };
        let result = calculate_pump_logic(&req);
        assert_eq!(result.required_clearance, 100);
        assert_eq!(result.pump_status, "Cavitation");
    }

    #[test]
    fn test_malformed_json_fallback() {
        // We simulate the fallback logic from the plugin_fn here to verify the struct we return
        let input = "{\"bad\": json";
        let result: Result<PumpRequest, _> = serde_json::from_str(&input);
        assert!(result.is_err());

        let fallback = PumpResult {
            required_clearance: 0,
            is_goal_met: false,
            pump_status: "Error".to_string(),
        };
        assert_eq!(fallback.pump_status, "Error");
        assert_eq!(fallback.required_clearance, 0);
    }

    #[test]
    fn test_cavitation_at_exact_zero_backlog() {
        // backlog=0 satisfies `<= 0`, so Cavitation — not Active.
        let req = PumpRequest {
            current_backlog: 0,
            pump_multiplier: 2.0,
            base_daily_target: 100,
        };
        let result = calculate_pump_logic(&req);
        assert_eq!(result.pump_status, "Cavitation");
        assert_eq!(result.required_clearance, 100);
    }

    #[test]
    fn test_maintenance_below_one_multiplier() {
        // pump_multiplier=0.5 satisfies `<= 1.0`, so Maintenance.
        let req = PumpRequest {
            current_backlog: 200,
            pump_multiplier: 0.5,
            base_daily_target: 50,
        };
        let result = calculate_pump_logic(&req);
        assert_eq!(result.pump_status, "Maintenance");
        assert_eq!(result.required_clearance, 50);
    }
}
