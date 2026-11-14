//! What a cron run leaves behind (#183, #245): a one-line, PII-free outcome per job in
//! `scheduler_election.last_status`, a PII-free `last_error` code, and the reason a
//! caller was refused (counted per New York day in `internal_refusals`).
//!
//! Pure functions only. Nothing here takes a phone number, a user id or message text,
//! and `merge_last_status` drops any segment it did not write.

use chrono::{DateTime, Utc};

use crate::gates::Reason;

/// `scheduler_election.last_status` is VARCHAR(255).
pub const LAST_STATUS_MAX: usize = 255;
/// Two segments and the "; " separator always fit in LAST_STATUS_MAX.
pub const SEGMENT_MAX: usize = 120;
/// Known jobs, in display order.
pub const JOBS: [&str; 2] = ["reminders", "sync"];

#[derive(Debug, Clone, PartialEq)]
pub enum ReminderOutcome {
    Sent,
    SendFailed,
    Gate { reason: Reason, phone_minutes: Option<i64>, nag_minutes: Option<i64>, nags_today: i64, cap: i64 },
    Error,
}

pub fn reminder_text(_o: &ReminderOutcome) -> String { String::new() }

#[derive(Debug, Clone, PartialEq)]
pub enum SyncOutcome { Fresh(i64), Scraped, ScrapeFailed, Error }

pub fn sync_text(_o: &SyncOutcome) -> String { String::new() }

/// "reminders 20:00Z: stood down (android active 35m)"
pub fn segment(_job: &str, _at: &DateTime<Utc>, _text: &str) -> String { String::new() }

/// Replace this job's segment in an existing last_status, keep the other job's.
pub fn merge_last_status(existing: Option<&str>, _segment: &str) -> String { existing.unwrap_or("").to_string() }

/// A send error reduced to something safe for a plaintext column.
pub fn pii_free_error(msg: &str) -> String { msg.to_string() }

/// The key that was committed to the public deploy scripts. It can never authorize again.
pub const BURNED_INTERNAL_KEY: &str = "test-internal-key";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Refusal { NoKey, BadKey, BurnedKey, BadSignature }

impl Refusal {
    pub fn code(self) -> &'static str {
        match self { Refusal::NoKey => "no_key", Refusal::BadKey => "bad_key", Refusal::BurnedKey => "burned_key", Refusal::BadSignature => "bad_signature" }
    }
}

/// Compare two secrets without an early exit on the first differing byte.
pub fn secret_eq(a: &str, b: &str) -> bool {
    a.len() == b.len() && a.bytes().zip(b.bytes()).fold(0u8, |acc, (x, y)| acc | (x ^ y)) == 0
}

/// The internal cron key check: the header or the `key` query parameter must equal the
/// configured key. An unset key authorizes nobody; neither does the published one.
pub fn check_internal_key(_cfg: &str, _header: Option<&str>, _query: Option<&str>) -> Result<(), Refusal> {
    Err(Refusal::NoKey)
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    const PHONE: &str = "+15551234567";
    const UID: &str = "c0a81a4b-115a-4eb6-bc2c-40908c58bf64";

    fn at(h: u32, m: u32) -> DateTime<Utc> { Utc.with_ymd_and_hms(2026, 11, 14, h, m, 0).unwrap() }

    fn gate(reason: Reason) -> ReminderOutcome {
        ReminderOutcome::Gate { reason, phone_minutes: Some(35), nag_minutes: Some(61), nags_today: 3, cap: 3 }
    }

    fn longest_digit_run(s: &str) -> usize {
        s.split(|c: char| !c.is_ascii_digit()).map(|r| r.len()).max().unwrap_or(0)
    }

    #[test]
    fn reminder_outcomes_read_as_reasons() {
        assert_eq!(reminder_text(&gate(Reason::PhoneActive)), "stood down (android active 35m)");
        assert_eq!(reminder_text(&gate(Reason::Damped)), "skipped (damped, last nag 61m ago)");
        assert_eq!(reminder_text(&gate(Reason::DailyCap)), "skipped (daily cap 3/3)");
        assert_eq!(reminder_text(&gate(Reason::OutsideWindow)), "skipped (outside window)");
        assert_eq!(reminder_text(&gate(Reason::PhoneUnverified)), "skipped (phone unverified)");
        assert_eq!(reminder_text(&ReminderOutcome::Sent), "sent 1");
        assert_eq!(reminder_text(&ReminderOutcome::SendFailed), "send failed");
        assert_eq!(reminder_text(&ReminderOutcome::Error), "error");
    }

    #[test]
    fn sync_outcomes_read_as_freshness() {
        assert_eq!(sync_text(&SyncOutcome::Fresh(40)), "fresh 40m");
        assert_eq!(sync_text(&SyncOutcome::Scraped), "scraped");
        assert_eq!(sync_text(&SyncOutcome::ScrapeFailed), "scrape failed");
    }

    #[test]
    fn segment_names_job_and_utc_time() {
        assert_eq!(segment("reminders", &at(20, 0), "sent 1"), "reminders 20:00Z: sent 1");
        assert_eq!(segment("sync", &at(20, 5), "fresh 40m"), "sync 20:05Z: fresh 40m");
        assert!(segment("sync", &at(20, 5), &"x".repeat(500)).chars().count() <= SEGMENT_MAX);
    }

    #[test]
    fn merge_keeps_both_jobs_and_replaces_its_own() {
        let r = segment("reminders", &at(20, 0), "stood down (android active 35m)");
        let s = segment("sync", &at(20, 5), "fresh 40m");
        assert_eq!(merge_last_status(None, &r), r);
        let both = merge_last_status(Some(&r), &s);
        assert_eq!(both, format!("{r}; {s}"));
        let r2 = segment("reminders", &at(22, 0), "skipped (outside window)");
        assert_eq!(merge_last_status(Some(&both), &r2), format!("{r2}; {s}"), "reminders first, sync kept");
        assert_eq!(merge_last_status(Some(&s), &r2), format!("{r2}; {s}"));
    }

    #[test]
    fn merge_stays_within_the_column() {
        let r = segment("reminders", &at(20, 0), &"r".repeat(300));
        let s = segment("sync", &at(20, 5), &"s".repeat(300));
        let m = merge_last_status(Some(&merge_last_status(None, &r)), &s);
        assert!(m.chars().count() <= LAST_STATUS_MAX, "{} chars", m.chars().count());
        assert!(m.contains("reminders 20:00Z") && m.contains("sync 20:05Z"));
        let junk = "z".repeat(1000);
        assert!(merge_last_status(Some(&junk), &s).chars().count() <= LAST_STATUS_MAX);
    }

    #[test]
    fn merge_drops_segments_it_did_not_write() {
        let foreign = format!("texted {PHONE} for {UID}: Daily Walk NOT FOUND; sync 20:05Z: fresh 40m");
        let m = merge_last_status(Some(&foreign), &segment("reminders", &at(20, 0), "sent 1"));
        assert_eq!(m, "reminders 20:00Z: sent 1; sync 20:05Z: fresh 40m");
    }

    #[test]
    fn outcomes_never_carry_a_number_uid_or_message() {
        let mut all: Vec<String> = Reason::ALL.iter().map(|r| reminder_text(&gate(*r))).collect();
        all.extend([ReminderOutcome::Sent, ReminderOutcome::SendFailed, ReminderOutcome::Error].iter().map(reminder_text));
        all.extend([SyncOutcome::Fresh(99), SyncOutcome::Scraped, SyncOutcome::ScrapeFailed, SyncOutcome::Error].iter().map(sync_text));
        for t in &all {
            assert!(!t.is_empty());
            assert!(longest_digit_run(t) < 7, "{t}");
            assert!(!t.contains(UID) && !t.contains("Daily Walk"), "{t}");
        }
    }

    #[test]
    fn send_errors_reduce_to_status_and_numeric_code() {
        assert_eq!(pii_free_error("twilio_http_400 code=21211"), "twilio_http_400 code=21211");
        assert_eq!(pii_free_error("twilio_http_502"), "twilio_http_502");
        assert_eq!(pii_free_error("whatsapp_sender_not_configured"), "whatsapp_sender_not_configured");
        assert_eq!(pii_free_error("whatsapp_template_not_configured"), "whatsapp_template_not_configured");
        assert_eq!(pii_free_error(&format!("The 'To' number {PHONE} is not valid")), "send_error");
        assert_eq!(pii_free_error("twilio_http_400 code=21211 +15551234567"), "send_error");
        assert_eq!(pii_free_error("Dec fail"), "send_error");
    }

    #[test]
    fn refusals_are_classified() {
        let k = "0123456789abcdef0123456789abcdef";
        assert_eq!(check_internal_key(k, None, None), Err(Refusal::NoKey));
        assert_eq!(check_internal_key(k, Some(""), Some("")), Err(Refusal::NoKey));
        assert_eq!(check_internal_key(k, Some("wrong"), None), Err(Refusal::BadKey));
        assert_eq!(check_internal_key(k, None, Some("wrong")), Err(Refusal::BadKey));
        assert_eq!(check_internal_key(k, Some(BURNED_INTERNAL_KEY), None), Err(Refusal::BurnedKey));
        assert_eq!(check_internal_key(k, None, Some(BURNED_INTERNAL_KEY)), Err(Refusal::BurnedKey));
        assert_eq!(check_internal_key(k, Some(k), None), Ok(()));
        assert_eq!(check_internal_key(k, None, Some(k)), Ok(()));
        assert_eq!(check_internal_key(k, Some("wrong"), Some(k)), Ok(()));
    }

    #[test]
    fn unset_or_published_key_authorizes_nobody() {
        assert_eq!(check_internal_key("", None, None), Err(Refusal::NoKey));
        assert_eq!(check_internal_key("", Some("anything"), None), Err(Refusal::BadKey));
        assert_eq!(check_internal_key(BURNED_INTERNAL_KEY, Some(BURNED_INTERNAL_KEY), None), Err(Refusal::BurnedKey));
        assert_eq!(check_internal_key(BURNED_INTERNAL_KEY, None, Some(BURNED_INTERNAL_KEY)), Err(Refusal::BurnedKey));
    }

    #[test]
    fn refusal_codes_are_the_table_vocabulary() {
        let codes: Vec<&str> = [Refusal::NoKey, Refusal::BadKey, Refusal::BurnedKey, Refusal::BadSignature].iter().map(|r| r.code()).collect();
        assert_eq!(codes, ["no_key", "bad_key", "burned_key", "bad_signature"]);
    }
}
