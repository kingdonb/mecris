use extism_pdk::*;
use serde::{Deserialize, Serialize};

#[derive(Deserialize, Debug)]
pub struct GoalStatus {
    pub slug: String,
    pub is_required_today: bool,
    pub is_completed: bool,
}

#[derive(Deserialize, Debug)]
pub struct AggregateRequest {
    pub goals: Vec<GoalStatus>,
}

#[derive(Serialize, Debug, PartialEq)]
pub struct AggregateResult {
    pub completed_count: i32,
    pub required_count: i32,
    pub all_clear: bool,
    pub status_message: String,
    pub template_id: Option<String>,
}

#[plugin_fn]
pub fn aggregate_status(input: String) -> FnResult<String> {
    let req: AggregateRequest = match serde_json::from_str(&input) {
        Ok(req) => req,
        Err(_) => {
            // Graceful fallback for malformed JSON
            let fallback = AggregateResult {
                completed_count: 0,
                required_count: 0,
                all_clear: false,
                status_message: "Error parsing aggregate request.".to_string(),
                template_id: None,
            };
            return Ok(serde_json::to_string(&fallback)?);
        }
    };

    let result = aggregate_status_logic(&req);
    Ok(serde_json::to_string(&result)?)
}

fn aggregate_status_logic(req: &AggregateRequest) -> AggregateResult {
    let mut required_count = 0;
    let mut completed_count = 0;

    for goal in &req.goals {
        if goal.is_required_today {
            required_count += 1;
            if goal.is_completed {
                completed_count += 1;
            }
        }
    }

    let all_clear = required_count > 0 && required_count == completed_count;
    
    let status_message = format!("{}/{} goals satisfied.", completed_count, required_count);
    
    let template_id = if all_clear {
        Some("MAJESTY_CAKE_CELEBRATION".to_string())
    } else {
        None
    };

    AggregateResult {
        completed_count,
        required_count,
        all_clear,
        status_message,
        template_id,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pending_state() {
        let req = AggregateRequest {
            goals: vec![
                GoalStatus { slug: "steps".to_string(), is_required_today: true, is_completed: true },
                GoalStatus { slug: "arabic".to_string(), is_required_today: true, is_completed: false },
                GoalStatus { slug: "greek".to_string(), is_required_today: true, is_completed: true },
            ],
        };
        let res = aggregate_status_logic(&req);
        assert_eq!(res.required_count, 3);
        assert_eq!(res.completed_count, 2);
        assert_eq!(res.all_clear, false);
        assert_eq!(res.status_message, "2/3 goals satisfied.");
        assert_eq!(res.template_id, None);
    }

    #[test]
    fn test_all_clear_state() {
        let req = AggregateRequest {
            goals: vec![
                GoalStatus { slug: "steps".to_string(), is_required_today: true, is_completed: true },
                GoalStatus { slug: "arabic".to_string(), is_required_today: true, is_completed: true },
            ],
        };
        let res = aggregate_status_logic(&req);
        assert_eq!(res.required_count, 2);
        assert_eq!(res.completed_count, 2);
        assert_eq!(res.all_clear, true);
        assert_eq!(res.status_message, "2/2 goals satisfied.");
        assert_eq!(res.template_id, Some("MAJESTY_CAKE_CELEBRATION".to_string()));
    }

    #[test]
    fn test_rest_day_state() {
        let req = AggregateRequest {
            goals: vec![
                GoalStatus { slug: "steps".to_string(), is_required_today: false, is_completed: false },
                GoalStatus { slug: "arabic".to_string(), is_required_today: false, is_completed: false },
            ],
        };
        let res = aggregate_status_logic(&req);
        assert_eq!(res.required_count, 0);
        assert_eq!(res.completed_count, 0);
        assert_eq!(res.all_clear, false); // A rest day yields no cake
        assert_eq!(res.status_message, "0/0 goals satisfied.");
        assert_eq!(res.template_id, None);
    }

    #[test]
    fn test_optional_goals_ignored() {
        let req = AggregateRequest {
            goals: vec![
                GoalStatus { slug: "steps".to_string(), is_required_today: true, is_completed: true },
                GoalStatus { slug: "optional-bonus".to_string(), is_required_today: false, is_completed: true },
            ],
        };
        let res = aggregate_status_logic(&req);
        assert_eq!(res.required_count, 1);
        assert_eq!(res.completed_count, 1);
        assert_eq!(res.all_clear, true); // The optional goal completion does not impact required_count
        assert_eq!(res.status_message, "1/1 goals satisfied.");
    }

    #[test]
    fn test_empty_goals_list() {
        // No goals at all — not a rest day, just an empty payload.
        // all_clear requires required_count > 0, so this must be false.
        let req = AggregateRequest { goals: vec![] };
        let res = aggregate_status_logic(&req);
        assert_eq!(res.required_count, 0);
        assert_eq!(res.completed_count, 0);
        assert_eq!(res.all_clear, false); // no required goals → no cake
        assert_eq!(res.status_message, "0/0 goals satisfied.");
        assert_eq!(res.template_id, None);
    }

    #[test]
    fn test_single_required_not_completed() {
        // One required goal, nothing done yet — 0/1 state.
        let req = AggregateRequest {
            goals: vec![
                GoalStatus { slug: "steps".to_string(), is_required_today: true, is_completed: false },
            ],
        };
        let res = aggregate_status_logic(&req);
        assert_eq!(res.required_count, 1);
        assert_eq!(res.completed_count, 0);
        assert_eq!(res.all_clear, false);
        assert_eq!(res.status_message, "0/1 goals satisfied.");
        assert_eq!(res.template_id, None);
    }

    #[test]
    fn test_all_optional_completed_yields_no_cake() {
        // Optional goals completed but no required goals — 0/0 state, no celebration.
        // all_clear requires required_count > 0.
        let req = AggregateRequest {
            goals: vec![
                GoalStatus { slug: "bonus-1".to_string(), is_required_today: false, is_completed: true },
                GoalStatus { slug: "bonus-2".to_string(), is_required_today: false, is_completed: true },
            ],
        };
        let res = aggregate_status_logic(&req);
        assert_eq!(res.required_count, 0);
        assert_eq!(res.completed_count, 0);
        assert_eq!(res.all_clear, false);
        assert_eq!(res.status_message, "0/0 goals satisfied.");
        assert_eq!(res.template_id, None);
    }

    #[test]
    fn test_required_and_optional_mix_only_required_counted() {
        // 1 required (completed) + 2 optional (1 completed, 1 not).
        // Only the required goal affects counts — all_clear = true.
        let req = AggregateRequest {
            goals: vec![
                GoalStatus { slug: "steps".to_string(), is_required_today: true, is_completed: true },
                GoalStatus { slug: "bonus-a".to_string(), is_required_today: false, is_completed: true },
                GoalStatus { slug: "bonus-b".to_string(), is_required_today: false, is_completed: false },
            ],
        };
        let res = aggregate_status_logic(&req);
        assert_eq!(res.required_count, 1);
        assert_eq!(res.completed_count, 1);
        assert_eq!(res.all_clear, true);
        assert_eq!(res.status_message, "1/1 goals satisfied.");
        assert_eq!(res.template_id, Some("MAJESTY_CAKE_CELEBRATION".to_string()));
    }

    #[test]
    fn test_many_required_partial_completion() {
        // 5 required goals, 3 completed — 3/5 state, no cake.
        let make = |slug: &str, req: bool, done: bool| GoalStatus {
            slug: slug.to_string(),
            is_required_today: req,
            is_completed: done,
        };
        let req = AggregateRequest {
            goals: vec![
                make("g1", true, true),
                make("g2", true, true),
                make("g3", true, true),
                make("g4", true, false),
                make("g5", true, false),
            ],
        };
        let res = aggregate_status_logic(&req);
        assert_eq!(res.required_count, 5);
        assert_eq!(res.completed_count, 3);
        assert_eq!(res.all_clear, false);
        assert_eq!(res.status_message, "3/5 goals satisfied.");
        assert_eq!(res.template_id, None);
    }
}
