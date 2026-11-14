//! Cloud walk-reminder gates (#368, #349, #166) and the failover-sync freshness gate (#183).
//!
//! Pure functions only: no I/O and no timestamp text parsing. Every age and count is
//! computed in SQL as a BIGINT and read through [`db_i64`]. All local times are
//! America/New_York, hard-coded per the operator ruling (lib.rs road_value_today);
//! `users.timezone` is not read. The truth table is contracts/nag_damping_cases.json.

use chrono::{DateTime, Timelike, Utc};
use chrono_tz::Tz;
use spin_sdk::pg::DbValue;

pub const NY: Tz = chrono_tz::America::New_York;
pub const DAMPING_MINUTES: i64 = 240;
pub const DEFAULT_STANDDOWN_MINUTES: i64 = 240;
pub const WALK_STEPS: i64 = 2000;
pub const FAILOVER_FRESH_MINUTES: i64 = 100;

/// A whole number (an age in minutes or a count) from a SQL value.
///
/// Postgres 14+ returns `EXTRACT(...) / 60` as NUMERIC, which Spin hands over as
/// `DbValue::Decimal`; a `::BIGINT` cast arrives as `Int64`. Both, and floats or
/// numeric text, floor to whole numbers. Text that is not a number (a timestamp,
/// say) is not a number of minutes: it is never parsed as a date.
pub fn db_i64(v: &DbValue) -> Option<i64> {
    fn from_text(s: &str) -> Option<i64> {
        let t = s.trim();
        if let Ok(i) = t.parse::<i64>() { return Some(i); }
        t.parse::<f64>().ok().filter(|f| f.is_finite()).map(|f| f.floor() as i64)
    }
    match v {
        DbValue::Int8(i) => Some(*i as i64),
        DbValue::Int16(i) => Some(*i as i64),
        DbValue::Int32(i) => Some(*i as i64),
        DbValue::Int64(i) => Some(*i),
        DbValue::Floating32(f) if f.is_finite() => Some(f.floor() as i64),
        DbValue::Floating64(f) if f.is_finite() => Some(f.floor() as i64),
        DbValue::Decimal(s) | DbValue::Str(s) => from_text(s),
        _ => None,
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Prefs {
    pub window_start: u32,
    pub window_end: u32,
    pub max_per_day: i64,
    pub enabled_days: Vec<String>,
    pub message_types: Option<Vec<String>>,
    pub vacation_mode: bool,
}

impl Default for Prefs {
    fn default() -> Self {
        Prefs { window_start: 13, window_end: 17, max_per_day: 3, enabled_days: Vec::new(), message_types: None, vacation_mode: false }
    }
}

impl Prefs {
    /// Parse `users.notification_prefs` text. NULL, `{}` or junk give the defaults;
    /// numbers may arrive as integers, floats or numeric strings.
    pub fn from_json(text: &str) -> Prefs {
        let d = Prefs::default();
        let v: serde_json::Value = match serde_json::from_str(text) { Ok(v) => v, Err(_) => return d };
        let Some(o) = v.as_object() else { return d };
        let num = |k: &str| -> Option<i64> {
            match o.get(k)? {
                serde_json::Value::Number(n) => n.as_i64().or_else(|| n.as_f64().filter(|f| f.is_finite()).map(|f| f.floor() as i64)),
                serde_json::Value::String(s) => s.trim().parse::<i64>().ok(),
                _ => None,
            }
        };
        let strings = |k: &str| -> Option<Vec<String>> {
            o.get(k)?.as_array().map(|a| a.iter().filter_map(|x| x.as_str().map(|s| s.to_string())).collect())
        };
        let hour = |k: &str, dflt: u32| num(k).filter(|h| (0..=23).contains(h)).map(|h| h as u32).unwrap_or(dflt);
        Prefs {
            window_start: hour("time_window_start", d.window_start),
            window_end: hour("time_window_end", d.window_end),
            max_per_day: num("max_messages_per_day").map(|n| n.max(0)).unwrap_or(d.max_per_day),
            enabled_days: strings("enabled_days").unwrap_or_default(),
            message_types: strings("message_types"),
            vacation_mode: o.get("vacation_mode").and_then(|b| b.as_bool()).unwrap_or(false),
        }
    }

    /// Both ends inclusive, as Python's reminder_service: 14..17 is 14:00 to 17:59.
    /// A start after the end wraps past midnight.
    fn hour_in_window(&self, h: u32) -> bool {
        if self.window_start <= self.window_end { self.window_start <= h && h <= self.window_end }
        else { h >= self.window_start || h <= self.window_end }
    }

    /// Absent or empty means every day. Full names and 3-letter abbreviations, any case.
    fn day_enabled(&self, weekday_abbrev: &str) -> bool {
        self.enabled_days.is_empty() || self.enabled_days.iter().any(|d| {
            let d = d.trim().to_lowercase();
            d.get(..3) == Some(weekday_abbrev)
        })
    }

    /// Absent means every type.
    fn type_enabled(&self, ty: &str) -> bool {
        self.message_types.as_ref().map_or(true, |ts| ts.iter().any(|t| t == ty))
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Verdict { Send, Skip, StandDown }

impl Verdict {
    pub fn code(self) -> &'static str {
        match self { Verdict::Send => "send", Verdict::Skip => "skip", Verdict::StandDown => "stand_down" }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Reason { Eligible, PhoneUnverified, Vacation, DayDisabled, TypeDisabled, OutsideWindow, WalkedToday, PhoneActive, Damped, DailyCap }

impl Reason {
    #[cfg(test)]
    pub const ALL: [Reason; 10] = [Reason::Eligible, Reason::PhoneUnverified, Reason::Vacation, Reason::DayDisabled, Reason::TypeDisabled, Reason::OutsideWindow, Reason::WalkedToday, Reason::PhoneActive, Reason::Damped, Reason::DailyCap];

    pub fn code(self) -> &'static str {
        match self {
            Reason::Eligible => "eligible",
            Reason::PhoneUnverified => "phone_unverified",
            Reason::Vacation => "vacation",
            Reason::DayDisabled => "day_disabled",
            Reason::TypeDisabled => "type_disabled",
            Reason::OutsideWindow => "outside_window",
            Reason::WalkedToday => "walked_today",
            Reason::PhoneActive => "phone_active",
            Reason::Damped => "damped",
            Reason::DailyCap => "daily_cap",
        }
    }

    pub fn verdict(self) -> Verdict {
        match self {
            Reason::Eligible => Verdict::Send,
            Reason::PhoneActive => Verdict::StandDown,
            _ => Verdict::Skip,
        }
    }
}

/// Everything the gates need for one user. Ages and counts come from SQL.
#[derive(Debug, Clone)]
pub struct GateInputs {
    pub now: DateTime<Utc>,
    pub prefs: Prefs,
    pub phone_verified: bool,
    /// `users.vacation_mode_until > now()`, computed in SQL.
    pub vacation_until_future: bool,
    /// Largest step count recorded for today's New York date.
    pub steps_today: i64,
    pub phone_heartbeat_minutes: Option<i64>,
    pub standdown_minutes: i64,
    pub minutes_since_last_nag: Option<i64>,
    pub nags_today: i64,
}

/// The first gate that blocks, or Eligible. Each contract case trips at most one gate,
/// so this order only decides which reason a real run reports when several apply.
pub fn decide(i: &GateInputs) -> Reason {
    let p = &i.prefs;
    if !i.phone_verified { return Reason::PhoneUnverified; }
    if p.vacation_mode || i.vacation_until_future { return Reason::Vacation; }
    if !p.day_enabled(&ny_weekday_abbrev(&i.now)) { return Reason::DayDisabled; }
    if !p.type_enabled("walk_reminder") { return Reason::TypeDisabled; }
    if !p.hour_in_window(ny_hour(&i.now)) { return Reason::OutsideWindow; }
    if i.steps_today >= WALK_STEPS { return Reason::WalkedToday; }
    if i.standdown_minutes > 0 && i.phone_heartbeat_minutes.is_some_and(|m| m < i.standdown_minutes) { return Reason::PhoneActive; }
    if i.minutes_since_last_nag.is_some_and(|m| m < DAMPING_MINUTES) { return Reason::Damped; }
    if i.nags_today >= p.max_per_day { return Reason::DailyCap; }
    Reason::Eligible
}

fn ny(now: &DateTime<Utc>) -> DateTime<Tz> { now.with_timezone(&NY) }
fn ny_weekday_abbrev(now: &DateTime<Utc>) -> String { ny(now).format("%a").to_string().to_lowercase() }

pub fn ny_hour(now: &DateTime<Utc>) -> u32 { ny(now).hour() }
/// Today's New York date. SQL computes the same as (now() AT TIME ZONE 'America/New_York')::DATE.
#[cfg(test)]
pub fn ny_date(now: &DateTime<Utc>) -> chrono::NaiveDate { ny(now).date_naive() }
/// The {{5}} slot of the walk reminder template.
pub fn ny_time_label(now: &DateTime<Utc>) -> String { ny(now).format("%I:%M %p").to_string() }
/// A human New York clock for the dry run, e.g. "2026-11-14 15:00 EST".
pub fn ny_clock(now: &DateTime<Utc>) -> String { ny(now).format("%Y-%m-%d %H:%M %Z").to_string() }

/// The `reminder_standdown_minutes` Spin variable. Empty or junk is the default; negative is 0.
pub fn standdown_minutes_from_var(s: &str) -> i64 {
    s.trim().parse::<i64>().map(|m| m.max(0)).unwrap_or(DEFAULT_STANDDOWN_MINUTES)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FailoverDecision { Scrape, Fresh(i64) }

/// Scrape when the newest language_stats.last_updated is FAILOVER_FRESH_MINUTES or older, or absent.
pub fn failover_decision(minutes_since_update: Option<i64>) -> FailoverDecision {
    match minutes_since_update {
        Some(m) if m < FAILOVER_FRESH_MINUTES => FailoverDecision::Fresh(m),
        _ => FailoverDecision::Scrape,
    }
}

/// message_log rows that damp: any type but phone_verification, outbound WhatsApp
/// (sent, failed or NULL status; a NULL channel is the column default 'whatsapp'),
/// or a local phone nag that was shown. Alias the table as `m`.
pub const DAMPING_ROWS_SQL: &str = "m.type <> 'phone_verification' AND ((COALESCE(m.channel, 'whatsapp') = 'whatsapp' AND (m.status IS NULL OR m.status IN ('sent', 'failed'))) OR (m.channel = 'android_native' AND m.status = 'shown'))";

/// message_log rows that count toward max_messages_per_day: outbound WhatsApp only.
/// The caller adds the New York date of `sent_at`, never the GMT `date` column.
pub const CAP_ROWS_SQL: &str = "m.type <> 'phone_verification' AND COALESCE(m.channel, 'whatsapp') = 'whatsapp' AND (m.status IS NULL OR m.status IN ('sent', 'failed'))";

/// A verification request is refused if the caller's newest phone_verification send is
/// younger than this many seconds.
pub const VERIFICATION_MIN_INTERVAL_SECS: i64 = 60;
/// At most this many verification sends per caller per America/New_York day.
pub const VERIFICATION_MAX_PER_DAY: i64 = 5;

/// Whether a phone verification request may send another code. `last_age_secs` is the age
/// of the caller's newest phone_verification row in message_log and `sent_today` the
/// count of those rows on the current New York day by sent_at, both BIGINT from SQL.
pub fn verification_allowed(last_age_secs: Option<i64>, sent_today: i64) -> bool {
    let recent = last_age_secs.is_some_and(|age| age < VERIFICATION_MIN_INTERVAL_SECS);
    !recent && sent_today < VERIFICATION_MAX_PER_DAY
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;
    use serde_json::Value;

    const CASES: &str = include_str!("../../../contracts/nag_damping_cases.json");

    fn ts(s: &str) -> DateTime<Utc> {
        DateTime::parse_from_rfc3339(s).expect("contract timestamp").with_timezone(&Utc)
    }

    fn utc(y: i32, mo: u32, d: u32, h: u32, mi: u32) -> DateTime<Utc> {
        Utc.with_ymd_and_hms(y, mo, d, h, mi, 0).unwrap()
    }

    // Test-side mirror of DAMPING_ROWS_SQL / CAP_ROWS_SQL, used to turn a contract's
    // message_log into the two numbers SQL hands the gates. CI checks the SQL itself.
    fn counts_for_damping(ty: &str, channel: Option<&str>, status: Option<&str>) -> bool {
        ty != "phone_verification" && match channel.unwrap_or("whatsapp") {
            "whatsapp" => matches!(status, None | Some("sent") | Some("failed")),
            "android_native" => status == Some("shown"),
            _ => false,
        }
    }

    fn counts_for_cap(ty: &str, channel: Option<&str>, status: Option<&str>) -> bool {
        ty != "phone_verification" && channel.unwrap_or("whatsapp") == "whatsapp" && matches!(status, None | Some("sent") | Some("failed"))
    }

    fn inputs_from_case(base: &Value, given: &Value) -> GateInputs {
        let mut m = base.as_object().unwrap().clone();
        for (k, v) in given.as_object().unwrap() { m.insert(k.clone(), v.clone()); }
        let now = ts(m["now"].as_str().unwrap());
        let prefs = Prefs::from_json(&m["prefs"].to_string());
        let vacation_until_future = m["vacation_mode_until"].as_str().map(|s| ts(s) > now).unwrap_or(false);
        let mut newest_nag: Option<DateTime<Utc>> = None;
        let mut nags_today = 0;
        for row in m["message_log"].as_array().unwrap() {
            let ty = row["type"].as_str().unwrap();
            let ch = row["channel"].as_str();
            let st = row["status"].as_str();
            let sent_at = ts(row["sent_at"].as_str().unwrap());
            if counts_for_damping(ty, ch, st) && newest_nag.map_or(true, |n| sent_at > n) { newest_nag = Some(sent_at); }
            if counts_for_cap(ty, ch, st) && ny_date(&sent_at) == ny_date(&now) { nags_today += 1; }
        }
        GateInputs {
            now,
            prefs,
            phone_verified: m["phone_verified"].as_bool().unwrap(),
            vacation_until_future,
            steps_today: if m["walked_today"].as_bool().unwrap() { 2500 } else { 0 },
            phone_heartbeat_minutes: m["phone_heartbeat_minutes"].as_i64(),
            standdown_minutes: m["reminder_standdown_minutes"].as_i64().unwrap(),
            // floor(seconds / 60), as FLOOR(EXTRACT(EPOCH FROM now() - MAX(sent_at)) / 60)::BIGINT
            minutes_since_last_nag: newest_nag.map(|t| (now - t).num_seconds().div_euclid(60)),
            nags_today,
        }
    }

    #[test]
    fn contract_nag_damping_cases_all_hold() {
        let doc: Value = serde_json::from_str(CASES).unwrap();
        let cases = doc["cases"].as_array().unwrap();
        assert!(cases.len() >= 40, "the contract should carry its full table");
        let mut failures = Vec::new();
        for c in cases {
            let name = c["name"].as_str().unwrap();
            let inputs = inputs_from_case(&doc["base"], &c["given"]);
            let reason = decide(&inputs);
            let (want_verdict, want_reason) = (c["expect"]["verdict"].as_str().unwrap(), c["expect"]["reason"].as_str().unwrap());
            if reason.code() != want_reason || reason.verdict().code() != want_verdict {
                failures.push(format!("{name}: got {}/{}, want {want_verdict}/{want_reason}", reason.verdict().code(), reason.code()));
            }
        }
        assert!(failures.is_empty(), "contract cases failed:\n{}", failures.join("\n"));
    }

    #[test]
    fn contract_vocabulary_matches_reason_enum() {
        let doc: Value = serde_json::from_str(CASES).unwrap();
        let mut codes: Vec<&str> = doc["reasons"].as_object().unwrap().keys().map(|k| k.as_str()).collect();
        let mut ours: Vec<&str> = Reason::ALL.iter().map(|r| r.code()).collect();
        codes.sort(); ours.sort();
        assert_eq!(codes, ours);
        assert_eq!(doc["constants"]["damping_minutes"].as_i64(), Some(DAMPING_MINUTES));
        assert_eq!(doc["constants"]["default_reminder_standdown_minutes"].as_i64(), Some(DEFAULT_STANDDOWN_MINUTES));
        assert_eq!(doc["constants"]["timezone"].as_str(), Some("America/New_York"));
        let d = &doc["constants"]["default_prefs"];
        let p = Prefs::from_json("{}");
        assert_eq!((p.window_start as i64, p.window_end as i64, p.max_per_day), (d["time_window_start"].as_i64().unwrap(), d["time_window_end"].as_i64().unwrap(), d["max_messages_per_day"].as_i64().unwrap()));
        for r in Reason::ALL {
            let want = match r { Reason::Eligible => Verdict::Send, Reason::PhoneActive => Verdict::StandDown, _ => Verdict::Skip };
            assert_eq!(r.verdict(), want, "{}", r.code());
        }
    }

    #[test]
    fn minutes_helper_decodes_int_decimal_and_float() {
        assert_eq!(db_i64(&DbValue::Int64(29)), Some(29));
        assert_eq!(db_i64(&DbValue::Int32(29)), Some(29));
        assert_eq!(db_i64(&DbValue::Decimal("29.6".to_string())), Some(29));
        assert_eq!(db_i64(&DbValue::Floating64(29.6)), Some(29));
        assert_eq!(db_i64(&DbValue::Str("29".to_string())), Some(29));
        assert_eq!(db_i64(&DbValue::Decimal("-0.5".to_string())), Some(-1), "a future row is negative minutes and still damps");
        assert_eq!(db_i64(&DbValue::DbNull), None);
    }

    #[test]
    fn minutes_helper_never_parses_timestamp_text() {
        // Neon prints timestamptz as '2026-11-14 17:59:57.363+00', which chrono rejects.
        // Ages come from SQL; text that is not a number is not an age.
        assert_eq!(db_i64(&DbValue::Str("2026-11-14 17:59:57.363+00".to_string())), None);
        assert_eq!(db_i64(&DbValue::Str(String::new())), None);
    }

    #[test]
    fn window_on_2026_11_14_est_with_prefs_14_to_17() {
        let prefs = Prefs::from_json(r#"{"time_window_start": 14, "time_window_end": 17, "max_messages_per_day": 3}"#);
        let at = |h, m| GateInputs { now: utc(2026, 11, 14, h, m), prefs: prefs.clone(), phone_verified: true, vacation_until_future: false, steps_today: 0, phone_heartbeat_minutes: None, standdown_minutes: 240, minutes_since_last_nag: None, nags_today: 0 };
        assert_eq!(decide(&at(18, 59)), Reason::OutsideWindow);
        assert_eq!(decide(&at(19, 0)), Reason::Eligible);
        assert_eq!(decide(&at(22, 59)), Reason::Eligible);
        assert_eq!(decide(&at(23, 0)), Reason::OutsideWindow);
        assert_eq!(ny_hour(&utc(2026, 11, 14, 19, 0)), 14);
    }

    #[test]
    fn today_at_0030_utc_is_the_previous_new_york_date() {
        assert_eq!(ny_date(&utc(2026, 11, 15, 0, 30)), chrono::NaiveDate::from_ymd_opt(2026, 11, 14).unwrap());
    }

    #[test]
    fn time_label_is_new_york_not_utc() {
        assert_eq!(ny_time_label(&utc(2026, 11, 14, 20, 0)), "03:00 PM");
        assert_eq!(ny_clock(&utc(2026, 11, 14, 20, 0)), "2026-11-14 15:00 EST");
        assert_eq!(ny_clock(&utc(2026, 7, 15, 18, 0)), "2026-07-15 14:00 EDT");
    }

    #[test]
    fn unverified_phone_is_ineligible_even_when_everything_else_passes() {
        let mut i = inputs_from_case(&serde_json::from_str::<Value>(CASES).unwrap()["base"], &serde_json::json!({}));
        assert_eq!(decide(&i), Reason::Eligible);
        i.phone_verified = false;
        assert_eq!(decide(&i), Reason::PhoneUnverified);
        assert_eq!(Reason::PhoneUnverified.verdict(), Verdict::Skip);
    }

    #[test]
    fn standdown_variable_parses_with_a_safe_default() {
        assert_eq!(standdown_minutes_from_var(""), 240);
        assert_eq!(standdown_minutes_from_var("junk"), 240);
        assert_eq!(standdown_minutes_from_var(" 60 "), 60);
        assert_eq!(standdown_minutes_from_var("0"), 0);
        assert_eq!(standdown_minutes_from_var("-5"), 0);
    }

    #[test]
    fn prefs_parse_live_shapes_and_tolerate_junk() {
        let live = Prefs::from_json(r#"{"time_window_start": 14, "time_window_end": 17, "max_messages_per_day": 3, "enabled_days": ["monday", "sunday"], "message_types": ["walk_reminder"], "vacation_mode": false}"#);
        assert_eq!((live.window_start, live.window_end, live.max_per_day), (14, 17, 3));
        assert_eq!(live.enabled_days, vec!["monday".to_string(), "sunday".to_string()]);
        assert_eq!(live.message_types, Some(vec!["walk_reminder".to_string()]));
        assert_eq!(Prefs::from_json("null"), Prefs::default());
        assert_eq!(Prefs::from_json("not json"), Prefs::default());
        assert_eq!(Prefs::from_json(r#"{"time_window_start": "15", "max_messages_per_day": 2.0}"#).window_start, 15);
        assert_eq!(Prefs::from_json(r#"{"max_messages_per_day": 2.0}"#).max_per_day, 2);
    }

    #[test]
    fn failover_gate_over_bigint_minutes() {
        assert_eq!(failover_decision(None), FailoverDecision::Scrape);
        assert_eq!(failover_decision(Some(99)), FailoverDecision::Fresh(99));
        assert_eq!(failover_decision(Some(100)), FailoverDecision::Scrape);
        assert_eq!(failover_decision(Some(0)), FailoverDecision::Fresh(0));
    }

    #[test]
    fn sql_predicates_name_every_rule() {
        for frag in ["phone_verification", "COALESCE(m.channel, 'whatsapp') = 'whatsapp'", "m.status IS NULL", "'sent'", "'failed'", "'android_native'", "'shown'"] {
            assert!(DAMPING_ROWS_SQL.contains(frag), "damping predicate lacks {frag}");
        }
        for frag in ["phone_verification", "COALESCE(m.channel, 'whatsapp') = 'whatsapp'", "m.status IS NULL", "'sent'", "'failed'"] {
            assert!(CAP_ROWS_SQL.contains(frag), "cap predicate lacks {frag}");
        }
        assert!(!CAP_ROWS_SQL.contains("android_native"), "local phone nags never count toward the WhatsApp cap");
    }

    #[test]
    fn verification_requests_are_throttled() {
        assert!(verification_allowed(None, 0), "a first request sends");
        assert!(verification_allowed(Some(61), 4), "a minute later, under the daily limit");
        assert!(!verification_allowed(Some(10), 1), "a second request inside a minute is refused");
        assert!(!verification_allowed(Some(60 * 60), VERIFICATION_MAX_PER_DAY), "the daily limit is a hard stop");
        assert!(!verification_allowed(Some(-5), 0), "a row stamped in the future counts as just now");
    }
}
