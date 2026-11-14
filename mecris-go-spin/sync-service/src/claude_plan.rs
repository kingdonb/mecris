//! Claude plan state (#344): the Rust twin of claude_plan_usage.derive_state and
//! summarize. The reference implementation is Python's; contracts/claude_plan_cases.json
//! holds both to the same answers.
//!
//! Pure functions only. The handler reads the caller's newest
//! claude_plan_usage_readings row (never the plaintext notes column), and passes the
//! database clock as `now` so the age and the freshness agree.

use chrono::{DateTime, Utc};
use serde::Serialize;

pub const CONSTRAINED_PCT: f64 = 80.0;
pub const EXHAUSTED_PCT: f64 = 100.0;
/// A reading strictly older than this is stale as a whole.
pub const MAX_READING_AGE_MINUTES: i64 = 24 * 60;

#[derive(Debug, Clone, PartialEq)]
pub struct Window {
    pub kind: String,
    pub pct_used: f64,
    /// As stored: Python's isoformat text.
    pub resets_at: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Reading {
    pub plan: Option<String>,
    pub verified: Option<bool>,
    pub source: Option<String>,
    pub observed_at: DateTime<Utc>,
    pub windows: Vec<Window>,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct WindowStatus {
    pub kind: String,
    pub pct_used: f64,
    pub resets_at: String,
    pub fresh: bool,
}

/// What aggregate-status and GET /claude-plan return.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct PlanStatus {
    pub state: &'static str,
    pub reason: String,
    pub stale: bool,
    pub summary_line: String,
    pub plan: Option<String>,
    pub verified: Option<bool>,
    pub source: Option<String>,
    pub observed_at: Option<String>,
    pub age_minutes: Option<i64>,
    pub windows: Vec<WindowStatus>,
}

/// Parse a stored windows JSONB value (as text). Windows without a string kind or a
/// numeric pct_used are dropped; a missing resets_at is kept as "" and is never fresh.
pub fn parse_windows(json: &str) -> Vec<Window> {
    let Ok(serde_json::Value::Array(items)) = serde_json::from_str::<serde_json::Value>(json) else { return Vec::new() };
    items.iter().filter_map(|w| {
        let kind = w.get("kind")?.as_str()?.to_string();
        let pct_used = w.get("pct_used")?.as_f64()?;
        let resets_at = w.get("resets_at").and_then(|r| r.as_str()).unwrap_or("").to_string();
        Some(Window { kind, pct_used, resets_at })
    }).collect()
}

/// Python's isoformat for a UTC instant: "2026-11-14T19:00:00+00:00", with microseconds
/// only when there are any.
pub fn isoformat(t: &DateTime<Utc>) -> String {
    if t.timestamp_subsec_micros() == 0 {
        t.format("%Y-%m-%dT%H:%M:%S+00:00").to_string()
    } else {
        t.format("%Y-%m-%dT%H:%M:%S%.6f+00:00").to_string()
    }
}

/// An ISO-8601 timestamp; like Python's _parse_dt, a value without an offset is UTC.
fn parse_ts(s: &str) -> Option<DateTime<Utc>> {
    let s = s.trim();
    DateTime::parse_from_rfc3339(s).ok().map(|t| t.with_timezone(&Utc))
        .or_else(|| chrono::NaiveDateTime::parse_from_str(s, "%Y-%m-%dT%H:%M:%S%.f").ok().map(|n| n.and_utc()))
}

/// Python's `%a %-I:%M %p` in America/New_York, e.g. "Mon 4:00 AM".
fn fmt_reset(t: &DateTime<Utc>) -> String {
    t.with_timezone(&chrono_tz::America::New_York).format("%a %-I:%M %p").to_string()
}

/// derive_state + summarize. `age_minutes` is the SQL age of the reading.
pub fn summarize(reading: Option<&Reading>, now: DateTime<Utc>, age_minutes: Option<i64>) -> PlanStatus {
    let unknown = |reason: &str, fresh: &[bool]| (STATE_UNKNOWN, reason.to_string(), true, format!("Claude: unknown ({reason})"), fresh.to_vec());
    let Some(r) = reading else {
        let (state, reason, stale, summary_line, _) = unknown("no reading recorded", &[]);
        return PlanStatus { state, reason, stale, summary_line, plan: None, verified: None, source: None, observed_at: None, age_minutes: None, windows: Vec::new() };
    };
    let all_stale = vec![false; r.windows.len()];
    let (state, reason, stale, summary_line, fresh) = if now - r.observed_at > chrono::Duration::minutes(MAX_READING_AGE_MINUTES) {
        unknown("reading is stale", &all_stale)
    } else {
        let fresh: Vec<bool> = r.windows.iter().map(|w| parse_ts(&w.resets_at).is_some_and(|reset| reset > now)).collect();
        let fresh_windows: Vec<&Window> = r.windows.iter().zip(&fresh).filter(|(_, f)| **f).map(|(w, _)| w).collect();
        match fresh_windows.iter().find(|w| w.kind == "weekly_all") {
            None => unknown("weekly window has reset since the last reading", &fresh),
            Some(weekly) => {
                // Python's max(): the first window with the highest pct_used binds.
                let mut worst = fresh_windows[0];
                for w in &fresh_windows[1..] { if w.pct_used > worst.pct_used { worst = w; } }
                let state = if worst.pct_used >= EXHAUSTED_PCT { STATE_EXHAUSTED } else if worst.pct_used > CONSTRAINED_PCT { STATE_CONSTRAINED } else { STATE_AVAILABLE };
                let reset = parse_ts(&weekly.resets_at).map(|t| fmt_reset(&t)).unwrap_or_default();
                let mut line = format!("Claude: {state} ({:.0}% weekly, resets {reset})", weekly.pct_used);
                if worst.kind != "weekly_all" && state != STATE_AVAILABLE {
                    line.push_str(&format!("; {} {:.0}%", worst.kind, worst.pct_used));
                }
                (state, format!("{} at {:.0}%", worst.kind, worst.pct_used), false, line, fresh)
            }
        }
    };
    PlanStatus {
        state, reason, stale, summary_line,
        plan: r.plan.clone(),
        verified: r.verified,
        source: r.source.clone(),
        observed_at: Some(isoformat(&r.observed_at)),
        age_minutes,
        windows: r.windows.iter().zip(fresh).map(|(w, fresh)| WindowStatus { kind: w.kind.clone(), pct_used: w.pct_used, resets_at: w.resets_at.clone(), fresh }).collect(),
    }
}

const STATE_AVAILABLE: &str = "available";
const STATE_CONSTRAINED: &str = "constrained";
const STATE_EXHAUSTED: &str = "exhausted";
const STATE_UNKNOWN: &str = "unknown";

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::Value;

    const CASES: &str = include_str!("../../../contracts/claude_plan_cases.json");

    fn ts(s: &str) -> DateTime<Utc> { DateTime::parse_from_rfc3339(s).expect("timestamp").with_timezone(&Utc) }

    fn reading_of(v: &Value) -> Option<Reading> {
        if v.is_null() { return None; }
        Some(Reading {
            plan: v["plan"].as_str().map(String::from),
            verified: v["verified"].as_bool(),
            source: v["source"].as_str().map(String::from),
            observed_at: ts(v["observed_at"].as_str().unwrap()),
            windows: parse_windows(&v["windows"].to_string()),
        })
    }

    #[test]
    fn every_contract_case_matches_python() {
        let cases: Value = serde_json::from_str(CASES).unwrap();
        for case in cases["cases"].as_array().unwrap() {
            let name = case["name"].as_str().unwrap();
            let now = ts(case["now"].as_str().unwrap());
            let reading = reading_of(&case["reading"]);
            let age = reading.as_ref().map(|r| (now - r.observed_at).num_minutes());
            let got = summarize(reading.as_ref(), now, age);
            let want = &case["expect"];
            assert_eq!(got.state, want["state"].as_str().unwrap(), "{name}: state");
            assert_eq!(got.reason, want["reason"].as_str().unwrap(), "{name}: reason");
            assert_eq!(got.stale, want["stale"].as_bool().unwrap(), "{name}: stale");
            assert_eq!(got.summary_line, want["summary_line"].as_str().unwrap(), "{name}: summary_line");
            // Python leaves expired windows out of fresh_windows; here every window carries `fresh`.
            let fresh: Vec<&str> = got.windows.iter().filter(|w| w.fresh).map(|w| w.kind.as_str()).collect();
            let want_fresh: Vec<&str> = want["fresh_window_kinds"].as_array().unwrap().iter().map(|k| k.as_str().unwrap()).collect();
            if got.stale && got.reason == "reading is stale" {
                // derive_state returns no fresh windows for a stale reading.
                assert!(want_fresh.is_empty(), "{name}");
            } else {
                assert_eq!(fresh, want_fresh, "{name}: fresh windows");
            }
            assert_eq!(got.age_minutes, age, "{name}: age");
            if let Some(r) = &reading {
                assert_eq!(got.windows.len(), r.windows.len(), "{name}: every stored window is reported");
                assert_eq!(got.plan, r.plan, "{name}");
                assert_eq!(got.observed_at.as_deref(), Some(isoformat(&r.observed_at).as_str()), "{name}");
            } else {
                assert!(got.windows.is_empty() && got.plan.is_none() && got.observed_at.is_none(), "{name}");
            }
        }
    }

    #[test]
    fn a_stale_reading_reports_no_fresh_window() {
        let cases: Value = serde_json::from_str(CASES).unwrap();
        let case = cases["cases"].as_array().unwrap().iter().find(|c| c["name"] == "over_24h_old").unwrap();
        let now = ts(case["now"].as_str().unwrap());
        let r = reading_of(&case["reading"]).unwrap();
        let got = summarize(Some(&r), now, Some(1441));
        assert!(got.windows.iter().all(|w| !w.fresh));
    }

    #[test]
    fn isoformat_matches_python() {
        assert_eq!(isoformat(&ts("2026-11-14T19:00:00Z")), "2026-11-14T19:00:00+00:00");
        assert_eq!(isoformat(&ts("2026-11-14T19:00:00.25Z")), "2026-11-14T19:00:00.250000+00:00");
    }

    #[test]
    fn parse_windows_keeps_well_formed_windows() {
        let w = parse_windows(r#"[{"kind":"weekly_all","pct_used":62,"resets_at":"2026-11-16T09:00:00+00:00"},{"kind":"session"},{"pct_used":3},{"kind":"weekly_fable","pct_used":1.5}]"#);
        assert_eq!(w, vec![
            Window { kind: "weekly_all".into(), pct_used: 62.0, resets_at: "2026-11-16T09:00:00+00:00".into() },
            Window { kind: "weekly_fable".into(), pct_used: 1.5, resets_at: String::new() },
        ]);
        assert!(parse_windows("not json").is_empty());
        assert!(parse_windows("{}").is_empty());
    }

    #[test]
    fn ties_bind_on_the_first_window_like_python_max() {
        let now = ts("2026-11-14T20:00:00Z");
        let r = Reading {
            plan: Some("ultra".into()), verified: None, source: Some("manual".into()), observed_at: ts("2026-11-14T19:00:00Z"),
            windows: vec![
                Window { kind: "weekly_all".into(), pct_used: 90.0, resets_at: "2026-11-16T09:00:00+00:00".into() },
                Window { kind: "session".into(), pct_used: 90.0, resets_at: "2026-11-14T23:00:00+00:00".into() },
            ],
        };
        let got = summarize(Some(&r), now, Some(60));
        assert_eq!(got.reason, "weekly_all at 90%");
        assert_eq!(got.summary_line, "Claude: constrained (90% weekly, resets Mon 4:00 AM)");
    }

    #[test]
    fn serializes_with_every_contract_key() {
        let now = ts("2026-11-14T20:00:00Z");
        let v = serde_json::to_value(summarize(None, now, None)).unwrap();
        let keys: Vec<&str> = v.as_object().unwrap().keys().map(|k| k.as_str()).collect();
        for k in ["state", "reason", "stale", "summary_line", "plan", "verified", "source", "observed_at", "age_minutes", "windows"] {
            assert!(keys.contains(&k), "missing {k}");
        }
        assert_eq!(v["summary_line"], "Claude: unknown (no reading recorded)");
    }
}
