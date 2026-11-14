//! Review pace (#344, #349): how many reviews are left today for each language goal and
//! the hourly pace that clears them by 22:00 America/New_York (hard-coded per the
//! operator ruling, like the reminder gates).
//!
//! Pure functions only. `remaining` is effective_targets' remaining (the larger of the
//! review pump's remainder and Beeminder's due-today); `due_today` is Beeminder's.

use chrono::{DateTime, Utc};
use serde::Serialize;

/// Reviews should be cleared by this New York hour.
pub const CLEAR_BY_HOUR: u32 = 22;
/// The goals aggregate-status reports, in order.
pub const PACE_GOALS: [&str; 2] = ["ARABIC", "GREEK"];

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Pace {
    pub goal: String,
    pub remaining: i32,
    /// Reviews per hour to clear `remaining` by `clear_by`, one decimal. In the last hour
    /// before 22:00 and after it, the whole remainder is due now: per_hour == remaining.
    pub per_hour: f64,
    /// Today's 22:00 in New York, RFC 3339 with the New York offset.
    pub clear_by: String,
    pub due_today: i32,
}

/// Pace for one goal.
pub fn pace(_goal: &str, _remaining: i32, _due_today: i32, _now: DateTime<Utc>) -> Pace {
    Pace { goal: String::new(), remaining: 0, per_hour: 0.0, clear_by: String::new(), due_today: 0 }
}

/// One language_stats row's pace inputs: (language_name, remaining, beeminder_due_today).
/// Returns PACE_GOALS that have a row, in PACE_GOALS order.
pub fn pace_for_goals(_rows: &[(String, i32, i32)], _now: DateTime<Utc>) -> Vec<Pace> {
    Vec::new()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn at(s: &str) -> DateTime<Utc> { DateTime::parse_from_rfc3339(s).unwrap().with_timezone(&Utc) }

    #[test]
    fn arabic_due_paces_to_22_new_york() {
        // 15:00 EST: seven hours left, 42 reviews -> 6 an hour.
        let p = pace("ARABIC", 42, 35, at("2026-11-14T20:00:00Z"));
        assert_eq!(p, Pace { goal: "ARABIC".into(), remaining: 42, per_hour: 6.0, clear_by: "2026-11-14T22:00:00-05:00".into(), due_today: 35 });
    }

    #[test]
    fn partial_hours_count() {
        // 19:30 EDT in summer: 2.5 hours left, 10 reviews -> 4 an hour; the offset is EDT.
        let p = pace("GREEK", 10, 0, at("2026-07-01T23:30:00Z"));
        assert_eq!(p.per_hour, 4.0);
        assert_eq!(p.clear_by, "2026-07-01T22:00:00-04:00");
        // 7 reviews over 3 hours rounds to one decimal.
        assert_eq!(pace("GREEK", 7, 0, at("2026-11-14T00:00:00Z")).per_hour, 2.3);
    }

    #[test]
    fn nothing_due_is_zero_pace() {
        let p = pace("GREEK", 0, 0, at("2026-11-14T20:00:00Z"));
        assert_eq!(p.per_hour, 0.0);
        assert_eq!(p.remaining, 0);
        assert_eq!(p.clear_by, "2026-11-14T22:00:00-05:00");
    }

    #[test]
    fn after_22_everything_is_due_now() {
        // 22:30 EST: past the clear-by time, today's 22:00 stays the deadline.
        let p = pace("ARABIC", 42, 35, at("2026-11-15T03:30:00Z"));
        assert_eq!(p.per_hour, 42.0);
        assert_eq!(p.clear_by, "2026-11-14T22:00:00-05:00");
        // Exactly 22:00 and the last hour before it: due now as well.
        assert_eq!(pace("ARABIC", 42, 0, at("2026-11-15T03:00:00Z")).per_hour, 42.0);
        assert_eq!(pace("ARABIC", 42, 0, at("2026-11-15T02:30:00Z")).per_hour, 42.0);
    }

    #[test]
    fn negative_inputs_read_as_nothing_due() {
        let p = pace("ARABIC", -3, -1, at("2026-11-14T20:00:00Z"));
        assert_eq!((p.remaining, p.due_today, p.per_hour), (0, 0, 0.0));
    }

    #[test]
    fn goals_come_in_order_and_only_when_present() {
        let now = at("2026-11-14T20:00:00Z");
        let rows = vec![("GREEK".to_string(), 0, 0), ("IRISH".to_string(), 50, 0), ("ARABIC".to_string(), 42, 35)];
        let goals: Vec<String> = pace_for_goals(&rows, now).into_iter().map(|p| p.goal).collect();
        assert_eq!(goals, ["ARABIC", "GREEK"]);
        assert_eq!(pace_for_goals(&[("GREEK".to_string(), 7, 0)], now).len(), 1);
        assert!(pace_for_goals(&[], now).is_empty());
    }
}
