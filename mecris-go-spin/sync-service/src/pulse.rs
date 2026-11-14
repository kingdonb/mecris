//! System pulse registry (#346): which scheduler_election roles the pulse shows, under
//! what name, and with what status. The truth table is contracts/pulse_roles.json; the
//! registry below is its Rust twin and the tests hold the two together.
//!
//! Pure functions only. Ages are whole minutes computed in SQL
//! (`FLOOR(EXTRACT(EPOCH FROM now() - heartbeat) / 60)::BIGINT`).

use serde::Serialize;

/// One scheduler_election row as the pulse reads it.
#[derive(Debug, Clone, PartialEq)]
pub struct Row {
    pub role: String,
    /// The user's own row (user_id = caller), as opposed to a NULL-user row.
    pub own: bool,
    /// Whole minutes since the heartbeat. Negative for a heartbeat in the future.
    pub minutes: i64,
    pub last_seen: String,
    pub last_status: Option<String>,
}

/// One pulse line, as aggregate-status serializes it.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Modality {
    pub role: String,
    pub status: String,
    pub last_seen: String,
    pub minutes_since: u64,
    pub last_status: Option<String>,
}

enum Lifecycle {
    /// Always shown: healthy under the first limit, degraded under the second, else offline.
    Expected { healthy_under: i64, degraded_under: i64 },
    /// Shown once as 'paused', whatever its age.
    Paused,
    /// Never shown.
    Retired,
}

/// contracts/pulse_roles.json `roles`.
const ROLES: [(&str, &str, Lifecycle); 6] = [
    ("leader", "MCP SERVER", Lifecycle::Expected { healthy_under: 2, degraded_under: 5 }),
    ("android_client", "ANDROID CLIENT", Lifecycle::Expected { healthy_under: 90, degraded_under: 240 }),
    ("akamai_functions", "AKAMAI FUNCTIONS", Lifecycle::Expected { healthy_under: 135, degraded_under: 250 }),
    ("active_ghost", "GHOST", Lifecycle::Paused),
    ("fermyon_cloud", "FERMYON CLOUD", Lifecycle::Retired),
    ("unknown_cloud", "UNKNOWN CLOUD", Lifecycle::Retired),
];
/// contracts/pulse_roles.json `unlisted_roles.show_under`.
const UNLISTED_SHOW_UNDER: i64 = 1440;

/// The display name and status for a role at an age, or None when the role is hidden.
pub fn verdict(role: &str, minutes: i64) -> Option<(String, &'static str)> {
    match ROLES.iter().find(|(r, _, _)| *r == role) {
        Some((_, display, lifecycle)) => match lifecycle {
            Lifecycle::Retired => None,
            Lifecycle::Paused => Some((display.to_string(), "paused")),
            Lifecycle::Expected { healthy_under, degraded_under } => {
                let status = if minutes < *healthy_under { "healthy" } else if minutes < *degraded_under { "degraded" } else { "offline" };
                Some((display.to_string(), status))
            }
        },
        None if minutes < UNLISTED_SHOW_UNDER => Some((role.replace('_', " ").to_uppercase(), "unknown")),
        None => None,
    }
}

/// Each role at most once: the newest heartbeat wins, the user's own row on a tie.
/// Visibility and status come from the winning row. Output is newest first.
pub fn modalities(rows: &[Row]) -> Vec<Modality> {
    let mut sorted: Vec<&Row> = rows.iter().collect();
    // Stable: equal (minutes, own) rows keep their SQL order.
    sorted.sort_by_key(|r| (r.minutes, !r.own));
    let mut seen: Vec<&str> = Vec::new();
    let mut out = Vec::new();
    for r in sorted {
        if seen.contains(&r.role.as_str()) { continue; }
        seen.push(&r.role);
        if let Some((display, status)) = verdict(&r.role, r.minutes) {
            out.push(Modality {
                role: display,
                status: status.to_string(),
                last_seen: r.last_seen.clone(),
                minutes_since: r.minutes.max(0) as u64,
                last_status: r.last_status.clone(),
            });
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::Value;

    const ROLES: &str = include_str!("../../../contracts/pulse_roles.json");

    fn table() -> Value { serde_json::from_str(ROLES).expect("pulse_roles.json") }

    fn expect_of(v: &Value) -> Option<(String, String)> {
        if v["visible"].as_bool().unwrap() {
            Some((v["display"].as_str().unwrap().to_string(), v["status"].as_str().unwrap().to_string()))
        } else {
            None
        }
    }

    #[test]
    fn every_contract_case_matches() {
        let t = table();
        for case in t["cases"].as_array().unwrap() {
            let role = case["role"].as_str().unwrap();
            let minutes = case["minutes"].as_i64().unwrap();
            let got = verdict(role, minutes).map(|(d, s)| (d, s.to_string()));
            assert_eq!(got, expect_of(&case["expect"]), "{role} at {minutes} min");
        }
    }

    #[test]
    fn registry_limits_match_the_contract() {
        // Every listed role, probed at its limits: the Rust registry cannot drift from the table.
        let t = table();
        for (role, entry) in t["roles"].as_object().unwrap() {
            let display = entry["display"].as_str().unwrap();
            match entry["lifecycle"].as_str().unwrap() {
                "retired" => assert_eq!(verdict(role, 0), None, "{role} is never shown"),
                "paused" => {
                    for m in [0, 1, 10_000_000] {
                        assert_eq!(verdict(role, m), Some((display.to_string(), "paused")), "{role} at {m}");
                    }
                }
                "expected" => {
                    let h = entry["healthy_under"].as_i64().unwrap();
                    let d = entry["degraded_under"].as_i64().unwrap();
                    assert_eq!(verdict(role, h - 1), Some((display.to_string(), "healthy")), "{role}");
                    assert_eq!(verdict(role, h), Some((display.to_string(), "degraded")), "{role}");
                    assert_eq!(verdict(role, d - 1), Some((display.to_string(), "degraded")), "{role}");
                    assert_eq!(verdict(role, d), Some((display.to_string(), "offline")), "{role}");
                }
                other => panic!("unknown lifecycle {other}"),
            }
        }
        let show_under = t["unlisted_roles"]["show_under"].as_i64().unwrap();
        assert_eq!(verdict("some_other_role", show_under - 1), Some(("SOME OTHER ROLE".to_string(), "unknown")));
        assert_eq!(verdict("some_other_role", show_under), None);
    }

    #[test]
    fn a_future_heartbeat_is_fresh() {
        assert_eq!(verdict("android_client", -1), Some(("ANDROID CLIENT".to_string(), "healthy")));
        assert_eq!(verdict("unknown", -1), Some(("UNKNOWN".to_string(), "unknown")));
    }

    fn row(role: &str, own: bool, minutes: i64) -> Row {
        Row { role: role.to_string(), own, minutes, last_seen: format!("t-{minutes}"), last_status: None }
    }

    #[test]
    fn duplicate_rows_show_each_role_once() {
        let t = table();
        for case in t["duplicate_cases"].as_array().unwrap() {
            let rows: Vec<Row> = case["rows"].as_array().unwrap().iter()
                .map(|r| row(r["role"].as_str().unwrap(), r["own"].as_bool().unwrap(), r["minutes"].as_i64().unwrap()))
                .collect();
            let got: Vec<(String, String, String)> = modalities(&rows).into_iter()
                .map(|m| (m.role, m.status, m.last_seen)).collect();
            // last_seen names the winning row: own rows and global rows differ only by it here.
            let want: Vec<(String, String, String)> = case["expect"].as_array().unwrap().iter().map(|e| {
                let minutes = e["minutes"].as_i64().unwrap();
                (e["display"].as_str().unwrap().to_string(), e["status"].as_str().unwrap().to_string(), format!("t-{minutes}"))
            }).collect();
            assert_eq!(got, want, "{}", case["name"]);
            // The winner is the expected row, own or not.
            for (m, e) in modalities(&rows).iter().zip(case["expect"].as_array().unwrap()) {
                let winner = rows.iter().filter(|r| r.last_seen == m.last_seen && r.own == e["own"].as_bool().unwrap()).count();
                assert_eq!(winner, 1, "{}: winner must be the {} row", case["name"], if e["own"].as_bool().unwrap() { "own" } else { "global" });
            }
        }
    }

    #[test]
    fn equal_heartbeat_prefers_the_own_row_whatever_the_input_order() {
        let mut own = row("leader", true, 3);
        own.last_status = Some("mine".into());
        let global = row("leader", false, 3);
        for rows in [vec![global.clone(), own.clone()], vec![own.clone(), global.clone()]] {
            let m = modalities(&rows);
            assert_eq!(m.len(), 1);
            assert_eq!(m[0].last_status.as_deref(), Some("mine"));
        }
    }

    #[test]
    fn modalities_are_newest_first_and_carry_last_status() {
        let mut akamai = row("akamai_functions", true, 60);
        akamai.last_status = Some("reminders 19:00Z: stood down (android active 35m)".into());
        let rows = vec![
            row("active_ghost", false, 22367),
            akamai,
            row("fermyon_cloud", true, 1),
            row("leader", true, 477),
            row("android_client", true, 42),
            row("unknown", true, 5000),
        ];
        let m = modalities(&rows);
        let names: Vec<&str> = m.iter().map(|x| x.role.as_str()).collect();
        assert_eq!(names, ["ANDROID CLIENT", "AKAMAI FUNCTIONS", "MCP SERVER", "GHOST"]);
        assert_eq!(m[1].last_status.as_deref(), Some("reminders 19:00Z: stood down (android active 35m)"));
        assert_eq!(m[0].last_status, None);
        assert_eq!(m[0].minutes_since, 42);
        assert_eq!(m[3].status, "paused");
    }

    #[test]
    fn a_future_heartbeat_reports_zero_minutes() {
        let m = modalities(&[row("akamai_functions", true, -1)]);
        assert_eq!(m[0].minutes_since, 0);
        assert_eq!(m[0].status, "healthy");
    }
}
