use extism_pdk::*;
use serde::{Deserialize, Serialize};

#[derive(Deserialize, Debug)]
pub struct Goal {
    pub slug: String,
    pub is_completed: bool,
    pub runway_hours: f64,
}

#[derive(Deserialize, Debug)]
pub struct NagRequest {
    pub goals: Vec<Goal>,
    pub idle_hours: f64,
    pub current_hour_local: i32,
    pub global_cooldown_active: bool,
}

#[derive(Serialize, Debug, PartialEq)]
pub struct NagResult {
    pub should_send: bool,
    pub tier: i32,
    pub template_id: String,
}

#[plugin_fn]
pub fn nag_ladder(input: String) -> FnResult<String> {
    let req: NagRequest = match serde_json::from_str(&input) {
        Ok(req) => req,
        Err(_) => {
            // Fallback gracefully on malformed JSON
            let fallback = NagResult {
                should_send: false,
                tier: 0,
                template_id: "ERROR_PARSING_PAYLOAD".to_string(),
            };
            return Ok(serde_json::to_string(&fallback)?);
        }
    };

    let result = nag_ladder_logic(&req);
    Ok(serde_json::to_string(&result)?)
}

fn nag_ladder_logic(req: &NagRequest) -> NagResult {
    let is_sleep_window = req.current_hour_local >= 22 || req.current_hour_local < 7;
    let mut highest_tier = 0;
    let mut final_template = "".to_string();

    // Tier 1 (Gentle): Uncompleted goal, off cooldown, not sleeping.
    // Tier 2 (Escalated): Tier 1 conditions AND idle_hours > 6.0.
    // Tier 3 (Emergency): Any goal runway_hours < 2.0 (overrides sleep/cooldown).

    for goal in &req.goals {
        let mut goal_tier = 0;
        let mut goal_template = "".to_string();

        if goal.runway_hours < 2.0 {
            // Tier 3 overrides everything
            goal_tier = 3;
            goal_template = "NAG_EMERGENCY".to_string();
        } else if !goal.is_completed {
            if !is_sleep_window && !req.global_cooldown_active {
                if req.idle_hours > 6.0 {
                    goal_tier = 2;
                    goal_template = "NAG_ESCALATED".to_string();
                } else {
                    goal_tier = 1;
                    goal_template = "NAG_GENTLE".to_string();
                }
            }
        }

        if goal_tier > highest_tier {
            highest_tier = goal_tier;
            final_template = goal_template;
        }
    }

    NagResult {
        should_send: highest_tier > 0,
        tier: highest_tier,
        template_id: final_template,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn req(runway: f64, completed: bool, idle: f64, hour: i32, cooldown: bool) -> NagRequest {
        NagRequest {
            goals: vec![Goal {
                slug: "test-goal".to_string(),
                is_completed: completed,
                runway_hours: runway,
            }],
            idle_hours: idle,
            current_hour_local: hour,
            global_cooldown_active: cooldown,
        }
    }

    #[test]
    fn test_sleep_window_suppression() {
        // 03:00 local time, incomplete goal, off cooldown, high idle.
        let r = req(12.0, false, 8.0, 3, false);
        let res = nag_ladder_logic(&r);
        assert_eq!(res.should_send, false);
        assert_eq!(res.tier, 0);
    }

    #[test]
    fn test_tier_3_emergency_override() {
        // 03:00 local time (sleep), high idle, ON cooldown, but runway < 2.0!
        let r = req(1.5, false, 8.0, 3, true);
        let res = nag_ladder_logic(&r);
        assert_eq!(res.should_send, true);
        assert_eq!(res.tier, 3);
        assert_eq!(res.template_id, "NAG_EMERGENCY");
    }

    #[test]
    fn test_tier_1_vs_tier_2_boundary() {
        // Not sleeping, off cooldown, incomplete goal.
        // idle = 6.0 exactly -> Tier 1
        let r1 = req(12.0, false, 6.0, 14, false);
        let res1 = nag_ladder_logic(&r1);
        assert_eq!(res1.should_send, true);
        assert_eq!(res1.tier, 1);
        assert_eq!(res1.template_id, "NAG_GENTLE");

        // idle = 6.1 -> Tier 2
        let r2 = req(12.0, false, 6.1, 14, false);
        let res2 = nag_ladder_logic(&r2);
        assert_eq!(res2.should_send, true);
        assert_eq!(res2.tier, 2);
        assert_eq!(res2.template_id, "NAG_ESCALATED");
    }

    #[test]
    fn test_priority_ordering() {
        let r = NagRequest {
            goals: vec![
                // Completed goal (Tier 0)
                Goal { slug: "g1".to_string(), is_completed: true, runway_hours: 24.0 },
                // Tier 1 trigger
                Goal { slug: "g2".to_string(), is_completed: false, runway_hours: 10.0 },
                // Tier 3 trigger
                Goal { slug: "g3".to_string(), is_completed: false, runway_hours: 1.5 },
            ],
            idle_hours: 5.0,
            current_hour_local: 15,
            global_cooldown_active: false,
        };
        let res = nag_ladder_logic(&r);
        assert_eq!(res.should_send, true);
        assert_eq!(res.tier, 3);
        assert_eq!(res.template_id, "NAG_EMERGENCY");
    }
}
