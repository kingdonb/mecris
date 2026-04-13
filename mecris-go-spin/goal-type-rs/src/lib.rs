use extism_pdk::*;
use serde::{Deserialize, Serialize};

#[derive(Deserialize, Debug)]
pub struct ValidationRequest {
    pub goal_slug: String,
    pub goal_type: String,
    pub current_value: f64,
    pub intended_push_value: f64,
}

#[derive(Serialize, Debug, PartialEq)]
pub struct ValidationResult {
    pub is_safe_to_push: bool,
    pub validated_delta: f64,
    pub status_message: String,
}

#[plugin_fn]
pub fn validate_push(input: String) -> FnResult<String> {
    let req: ValidationRequest = match serde_json::from_str(&input) {
        Ok(req) => req,
        Err(_) => {
            // Graceful fallback for malformed JSON
            let fallback = ValidationResult {
                is_safe_to_push: false,
                validated_delta: 0.0,
                status_message: "Error parsing validation request.".to_string(),
            };
            return Ok(serde_json::to_string(&fallback)?);
        }
    };

    let result = validate_push_logic(&req);
    Ok(serde_json::to_string(&result)?)
}

fn validate_push_logic(req: &ValidationRequest) -> ValidationResult {
    match req.goal_type.as_str() {
        "odometer" => {
            let delta = req.intended_push_value - req.current_value;
            
            if req.intended_push_value < req.current_value {
                ValidationResult {
                    is_safe_to_push: false,
                    validated_delta: delta,
                    status_message: "Regression detected: Intended odometer value is less than current value.".to_string(),
                }
            } else if req.intended_push_value == req.current_value {
                ValidationResult {
                    is_safe_to_push: false,
                    validated_delta: delta,
                    status_message: "Zero delta redundant: Odometer value unchanged.".to_string(),
                }
            } else {
                ValidationResult {
                    is_safe_to_push: true,
                    validated_delta: delta,
                    status_message: "Safe to push odometer.".to_string(),
                }
            }
        },
        "backlog" => {
            // Delta for backlog is technically current - intended (as intended is lower if you did work), 
            // but safety is true either way.
            let delta = req.current_value - req.intended_push_value;
            ValidationResult {
                is_safe_to_push: true,
                validated_delta: delta,
                status_message: "Safe to push backlog snapshot.".to_string(),
            }
        },
        _ => {
            // Fail closed on unknown types
            ValidationResult {
                is_safe_to_push: false,
                validated_delta: 0.0,
                status_message: format!("Unknown goal type: fail closed. Received '{}'", req.goal_type),
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn req(g_type: &str, current: f64, intended: f64) -> ValidationRequest {
        ValidationRequest {
            goal_slug: "test-goal".to_string(),
            goal_type: g_type.to_string(),
            current_value: current,
            intended_push_value: intended,
        }
    }

    #[test]
    fn test_odometer_valid_push() {
        let r = req("odometer", 100.0, 110.0);
        let res = validate_push_logic(&r);
        assert_eq!(res.is_safe_to_push, true);
        assert_eq!(res.validated_delta, 10.0);
        assert_eq!(res.status_message, "Safe to push odometer.");
    }

    #[test]
    fn test_odometer_regression() {
        let r = req("odometer", 100.0, 95.0); // snapshot bug!
        let res = validate_push_logic(&r);
        assert_eq!(res.is_safe_to_push, false); // blocked!
        assert_eq!(res.validated_delta, -5.0);
        assert!(res.status_message.contains("Regression"));
    }

    #[test]
    fn test_odometer_redundant_zero_delta() {
        let r = req("odometer", 100.0, 100.0);
        let res = validate_push_logic(&r);
        assert_eq!(res.is_safe_to_push, false); // blocked!
        assert_eq!(res.validated_delta, 0.0);
        assert!(res.status_message.contains("redundant"));
    }

    #[test]
    fn test_backlog_snapshot() {
        // Backlogs are snapshots, so decreasing values are valid.
        let r = req("backlog", 50.0, 45.0);
        let res = validate_push_logic(&r);
        assert_eq!(res.is_safe_to_push, true);
        assert_eq!(res.validated_delta, 5.0); // current - intended
    }

    #[test]
    fn test_unknown_goal_type_fails_closed() {
        let r = req("fatbot", 100.0, 110.0);
        let res = validate_push_logic(&r);
        assert_eq!(res.is_safe_to_push, false); // safety valve activates!
    }

    #[test]
    fn test_backlog_increases() {
        // Backlog grew (more work accumulated): current=45, intended=50.
        // Unlike odometer, this is still safe to push — it's just a snapshot.
        // delta = current - intended = 45 - 50 = -5 (negative: backlog grew)
        let r = req("backlog", 45.0, 50.0);
        let res = validate_push_logic(&r);
        assert_eq!(res.is_safe_to_push, true);
        assert_eq!(res.validated_delta, -5.0);
        assert_eq!(res.status_message, "Safe to push backlog snapshot.");
    }

    #[test]
    fn test_backlog_zero_delta() {
        // Backlog unchanged: current == intended. Safe for backlog (unlike odometer zero delta).
        // delta = current - intended = 0
        let r = req("backlog", 50.0, 50.0);
        let res = validate_push_logic(&r);
        assert_eq!(res.is_safe_to_push, true);
        assert_eq!(res.validated_delta, 0.0);
        assert_eq!(res.status_message, "Safe to push backlog snapshot.");
    }
}
