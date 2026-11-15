//! Phase 1 of docs/WALK_REMINDERS.md (#363): see what happens to every reminder.
//!
//! Pure functions only: request validation, the forward-only WhatsApp delivery status,
//! Twilio form and response parsing. lib.rs does the I/O. The shapes are
//! contracts/message_events.json. Nothing here keeps message text, phone numbers or names:
//! the only values that leave these functions are ids, vocabulary words, times and codes.

use chrono::{DateTime, Utc};

/// Notification events the phone reports through POST /internal/log-message-event.
pub const PHONE_EVENTS: [&str; 4] = ["tapped", "dismissed", "action_later", "action_start"];
/// Twilio delivery statuses we keep, in forward order; the last two are terminal.
pub const WHATSAPP_STATUSES: [&str; 6] = ["queued", "sent", "delivered", "read", "undelivered", "failed"];
/// A phone-reported event time older than this is not trusted; the event is stamped now.
pub const EVENT_MAX_AGE_SECS: i64 = 24 * 60 * 60;
/// Longest client_ref accepted.
pub const CLIENT_REF_MAX: usize = 64;

/// client_ref_rule: 1-64 characters from [A-Za-z0-9-].
pub fn valid_client_ref(s: &str) -> bool {
    let _ = s;
    todo!("#363")
}

/// The optional `client_ref` of a log-message body. Absent or JSON null is None (old
/// clients); anything else must be a string matching client_ref_rule.
pub fn log_message_client_ref(body: &[u8]) -> Result<Option<String>, &'static str> {
    let _ = body;
    todo!("#363")
}

/// A validated POST /internal/log-message-event body. `at_ms` is the event time in epoch
/// milliseconds, kept exactly so a retried upload hits the same UNIQUE row; None means now.
#[derive(Debug, PartialEq)]
pub struct PhoneEvent { pub client_ref: String, pub event: &'static str, pub at_ms: Option<i64> }

pub fn validate_phone_event(body: &[u8], now: DateTime<Utc>) -> Result<PhoneEvent, &'static str> {
    let _ = (body, now);
    todo!("#363")
}

/// The vocabulary word for a Twilio status, or None for one we do not track
/// (accepted, sending, scheduled, ...).
pub fn whatsapp_status(s: &str) -> Option<&'static str> {
    let _ = s;
    todo!("#363")
}

/// Whether `new` may replace `current` in message_log.delivery_status: forward only,
/// queued < sent < delivered < read; undelivered and failed are terminal and replace
/// anything below them. An unknown or missing current status accepts any known one.
pub fn status_advances(current: Option<&str>, new: &str) -> bool {
    let _ = (current, new);
    todo!("#363")
}

/// A Twilio message SID: two capital letters and 32 hex digits (SM..., MM...).
pub fn valid_message_sid(s: &str) -> bool {
    let _ = s;
    todo!("#363")
}

/// A signature-verified Twilio status callback. `status` is None for a status we do not
/// track; `error_code` is set only for a numeric, non-empty ErrorCode.
#[derive(Debug, PartialEq)]
pub struct StatusCallback { pub sid: String, pub status: Option<&'static str>, pub error_code: Option<i64> }

pub fn parse_status_callback(form: &[(String, String)]) -> Result<StatusCallback, &'static str> {
    let _ = form;
    todo!("#363")
}

/// What Spin keeps from Twilio's answer to a send: the SID (when it looks like one) and
/// the initial delivery status ('queued' unless Twilio said a tracked status).
#[derive(Debug, PartialEq)]
pub struct SendReceipt { pub sid: Option<String>, pub status: &'static str }

pub fn parse_send_receipt(body: &str) -> SendReceipt {
    let _ = body;
    todo!("#363")
}

/// A Twilio Messages form with `StatusCallback` appended when `callback_url` is set.
/// An empty or blank URL sends no StatusCallback at all.
pub fn with_status_callback(form: String, callback_url: &str) -> String {
    let _ = callback_url;
    form
}

/// `notifications_enabled` from a heartbeat body: Some only when present and boolean.
pub fn heartbeat_notifications_enabled(body: &serde_json::Value) -> Option<bool> {
    let _ = body;
    todo!("#363")
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{json, Value};

    const CONTRACT: &str = include_str!("../../../contracts/message_events.json");

    fn contract() -> Value { serde_json::from_str(CONTRACT).expect("contract is JSON") }
    fn utc(s: &str) -> DateTime<Utc> { DateTime::parse_from_rfc3339(s).unwrap().with_timezone(&Utc) }
    fn form(pairs: &[(&str, &str)]) -> Vec<(String, String)> { pairs.iter().map(|(k, v)| (k.to_string(), v.to_string())).collect() }
    fn words(v: &Value) -> Vec<String> { v.as_array().unwrap().iter().map(|w| w.as_str().unwrap().to_string()).collect() }

    // --- the contract's own examples ---

    #[test]
    fn contract_vocabulary_matches() {
        let c = contract();
        assert_eq!(words(&c["event_vocabulary"]["phone"]), PHONE_EVENTS);
        assert_eq!(words(&c["event_vocabulary"]["whatsapp"]), WHATSAPP_STATUSES);
    }

    #[test]
    fn contract_log_message_example_carries_a_valid_client_ref() {
        let c = contract();
        let body = c["api"]["log_message"]["request_example"].to_string();
        assert_eq!(log_message_client_ref(body.as_bytes()), Ok(Some("3f2b8c1e-7a4d-4e0b-9c55-2b1f0d6a9e11".to_string())));
    }

    #[test]
    fn contract_log_message_event_example_validates() {
        let c = contract();
        let body = c["api"]["log_message_event"]["request_example"].to_string();
        let now = utc("2026-11-15T19:10:00Z");
        let ev = validate_phone_event(body.as_bytes(), now).unwrap();
        assert_eq!(ev.client_ref, "3f2b8c1e-7a4d-4e0b-9c55-2b1f0d6a9e11");
        assert_eq!(ev.event, "action_later");
        assert_eq!(ev.at_ms, Some(utc("2026-11-15T19:05:40Z").timestamp_millis()));
    }

    #[test]
    fn contract_heartbeat_example_reports_notifications() {
        let c = contract();
        assert_eq!(heartbeat_notifications_enabled(&c["api"]["heartbeat"]["request_example"]), Some(true));
    }

    #[test]
    fn contract_status_callback_example_parses() {
        let c = contract();
        let ex = c["api"]["twilio_status_callback"]["request_form_example"].as_object().unwrap();
        let f: Vec<(String, String)> = ex.iter().map(|(k, v)| (k.clone(), v.as_str().unwrap().to_string())).collect();
        assert_eq!(parse_status_callback(&f), Ok(StatusCallback { sid: "SM0123456789abcdef0123456789abcdef".into(), status: Some("delivered"), error_code: None }));
    }

    // --- client_ref ---

    #[test]
    fn client_ref_rule() {
        assert!(valid_client_ref("3f2b8c1e-7a4d-4e0b-9c55-2b1f0d6a9e11"));
        assert!(valid_client_ref("a"));
        assert!(valid_client_ref(&"A-9".repeat(21)));
        assert!(valid_client_ref(&"x".repeat(CLIENT_REF_MAX)));
        assert!(!valid_client_ref(""));
        assert!(!valid_client_ref(&"x".repeat(CLIENT_REF_MAX + 1)));
        for bad in ["has space", "under_score", "dot.ted", "slash/", "é", "+15005550006", "x\n", " lead"] {
            assert!(!valid_client_ref(bad), "{bad:?}");
        }
    }

    #[test]
    fn log_message_client_ref_is_optional_but_checked() {
        let cr = |v: Value| log_message_client_ref(v.to_string().as_bytes());
        assert_eq!(cr(json!({"type": "walk_reminder"})), Ok(None), "old clients omit it");
        assert_eq!(cr(json!({"type": "walk_reminder", "client_ref": null})), Ok(None));
        assert_eq!(cr(json!({"type": "walk_reminder", "client_ref": "abc-123"})), Ok(Some("abc-123".into())));
        for bad in [json!(""), json!("bad ref"), json!(12), json!(["a"]), json!("x".repeat(65))] {
            assert!(cr(json!({"type": "walk_reminder", "client_ref": bad})).is_err(), "{bad}");
        }
    }

    // --- log-message-event bodies ---

    #[test]
    fn phone_event_accepts_the_phone_vocabulary_only() {
        let now = utc("2026-11-15T19:10:00Z");
        for e in PHONE_EVENTS {
            let b = json!({"client_ref": "r-1", "event": e}).to_string();
            assert_eq!(validate_phone_event(b.as_bytes(), now), Ok(PhoneEvent { client_ref: "r-1".into(), event: e, at_ms: None }), "{e}");
        }
        for e in ["shown", "delivered", "read", "TAPPED", "action:LATER", "action_snooze", ""] {
            let b = json!({"client_ref": "r-1", "event": e}).to_string();
            assert!(validate_phone_event(b.as_bytes(), now).is_err(), "{e}");
        }
    }

    #[test]
    fn phone_event_refuses_bad_bodies() {
        let now = utc("2026-11-15T19:10:00Z");
        for b in [
            json!({"event": "tapped"}).to_string(),
            json!({"client_ref": "bad ref", "event": "tapped"}).to_string(),
            json!({"client_ref": 7, "event": "tapped"}).to_string(),
            json!({"client_ref": "r-1"}).to_string(),
            json!({"client_ref": "r-1", "event": 1}).to_string(),
            json!(["tapped"]).to_string(),
            "client_ref=r-1&event=tapped".to_string(),
            String::new(),
        ] {
            assert!(validate_phone_event(b.as_bytes(), now).is_err(), "{b}");
        }
    }

    #[test]
    fn phone_event_ignores_a_user_in_the_body() {
        let now = utc("2026-11-15T19:10:00Z");
        let b = json!({"client_ref": "r-1", "event": "tapped", "user_id": "someone-else"}).to_string();
        assert_eq!(validate_phone_event(b.as_bytes(), now), Ok(PhoneEvent { client_ref: "r-1".into(), event: "tapped", at_ms: None }));
    }

    #[test]
    fn phone_event_at_is_clamped_to_the_last_24_hours() {
        let now = utc("2026-11-15T19:10:00Z");
        let at = |v: Value| validate_phone_event(json!({"client_ref": "r-1", "event": "tapped", "at": v}).to_string().as_bytes(), now).map(|e| e.at_ms);
        assert_eq!(at(json!("2026-11-15T19:05:40Z")), Ok(Some(utc("2026-11-15T19:05:40Z").timestamp_millis())));
        assert_eq!(at(json!("2026-11-15T19:05:40.250Z")), Ok(Some(utc("2026-11-15T19:05:40Z").timestamp_millis() + 250)), "milliseconds are kept");
        assert_eq!(at(json!("2026-11-15T14:05:40-05:00")), Ok(Some(utc("2026-11-15T19:05:40Z").timestamp_millis())), "offsets are honoured");
        assert_eq!(at(json!("2026-11-14T19:10:00Z")), Ok(Some(utc("2026-11-14T19:10:00Z").timestamp_millis())), "exactly 24 h old is kept");
        assert_eq!(at(json!("2026-11-14T19:09:59Z")), Ok(None), "older than 24 h means now");
        assert_eq!(at(json!("2026-11-15T19:10:01Z")), Ok(None), "the future means now");
        assert_eq!(at(json!("soon")), Ok(None));
        assert_eq!(at(json!(1763233540)), Ok(None));
        assert_eq!(at(Value::Null), Ok(None));
    }

    // --- delivery status ---

    #[test]
    fn whatsapp_status_knows_the_vocabulary_only() {
        for s in WHATSAPP_STATUSES { assert_eq!(whatsapp_status(s), Some(s)); }
        for s in ["accepted", "sending", "scheduled", "canceled", "receiving", "received", "DELIVERED", ""] {
            assert_eq!(whatsapp_status(s), None, "{s}");
        }
    }

    #[test]
    fn status_moves_forward_only() {
        assert!(status_advances(None, "queued"));
        assert!(status_advances(None, "read"));
        assert!(status_advances(Some("queued"), "sent"));
        assert!(status_advances(Some("queued"), "read"), "skipping a step is forward");
        assert!(status_advances(Some("sent"), "delivered"));
        assert!(status_advances(Some("delivered"), "read"));
        assert!(!status_advances(Some("read"), "delivered"), "a late 'delivered' never undoes 'read'");
        assert!(!status_advances(Some("delivered"), "sent"));
        assert!(!status_advances(Some("sent"), "sent"), "a repeat changes nothing");
        assert!(!status_advances(Some("read"), "read"));
    }

    #[test]
    fn terminal_statuses_replace_anything_below_and_then_stick() {
        for below in ["queued", "sent", "delivered", "read"] {
            assert!(status_advances(Some(below), "failed"), "{below} -> failed");
            assert!(status_advances(Some(below), "undelivered"), "{below} -> undelivered");
        }
        for terminal in ["failed", "undelivered"] {
            for later in WHATSAPP_STATUSES {
                assert!(!status_advances(Some(terminal), later), "{terminal} -> {later}");
            }
        }
    }

    #[test]
    fn unknown_statuses_never_land_and_never_block() {
        assert!(!status_advances(None, "sending"));
        assert!(!status_advances(Some("queued"), "accepted"));
        assert!(status_advances(Some("accepted"), "queued"), "an untracked current value accepts a tracked one");
    }

    // --- Twilio SIDs and responses ---

    #[test]
    fn message_sid_shape() {
        assert!(valid_message_sid("SM0123456789abcdef0123456789abcdef"));
        assert!(valid_message_sid("MM0123456789ABCDEF0123456789ABCDEF"));
        for bad in ["", "SM", "SM0123456789abcdef0123456789abcde", "SM0123456789abcdef0123456789abcdef0", "sm0123456789abcdef0123456789abcdef", "SM0123456789abcdef0123456789abcdeg", "SM 123456789abcdef0123456789abcdef"] {
            assert!(!valid_message_sid(bad), "{bad:?}");
        }
    }

    #[test]
    fn send_receipt_keeps_sid_and_tracked_status() {
        let r = parse_send_receipt(&json!({"sid": "SM0123456789abcdef0123456789abcdef", "status": "queued", "to": "whatsapp:+15005550006", "body": "text"}).to_string());
        assert_eq!(r, SendReceipt { sid: Some("SM0123456789abcdef0123456789abcdef".into()), status: "queued" });
        let r = parse_send_receipt(&json!({"sid": "SM0123456789abcdef0123456789abcdef", "status": "sent"}).to_string());
        assert_eq!(r.status, "sent");
        let r = parse_send_receipt(&json!({"sid": "SM0123456789abcdef0123456789abcdef", "status": "accepted"}).to_string());
        assert_eq!(r.status, "queued", "an untracked initial status is stored as queued");
    }

    #[test]
    fn send_receipt_survives_junk() {
        assert_eq!(parse_send_receipt(""), SendReceipt { sid: None, status: "queued" });
        assert_eq!(parse_send_receipt("not json"), SendReceipt { sid: None, status: "queued" });
        assert_eq!(parse_send_receipt(&json!({"sid": 5}).to_string()).sid, None);
        assert_eq!(parse_send_receipt(&json!({"sid": "whatsapp:+15005550006"}).to_string()).sid, None, "only a SID-shaped value is stored");
    }

    // --- status callback forms ---

    #[test]
    fn status_callback_form_parsing() {
        let sid = "SM0123456789abcdef0123456789abcdef";
        assert_eq!(parse_status_callback(&form(&[("MessageSid", sid), ("MessageStatus", "failed"), ("ErrorCode", "63051")])),
            Ok(StatusCallback { sid: sid.into(), status: Some("failed"), error_code: Some(63051) }));
        assert_eq!(parse_status_callback(&form(&[("MessageSid", sid), ("MessageStatus", "read")])),
            Ok(StatusCallback { sid: sid.into(), status: Some("read"), error_code: None }));
        assert_eq!(parse_status_callback(&form(&[("MessageSid", sid), ("MessageStatus", "sending"), ("ErrorCode", "")])),
            Ok(StatusCallback { sid: sid.into(), status: None, error_code: None }), "an untracked status parses, and changes nothing");
        assert_eq!(parse_status_callback(&form(&[("MessageSid", sid), ("MessageStatus", "undelivered"), ("ErrorCode", "abc")])).unwrap().error_code, None);
        // SmsSid/SmsStatus are Twilio's older names for the same fields; we read only the new ones.
        assert!(parse_status_callback(&form(&[("SmsSid", sid), ("SmsStatus", "sent")])).is_err());
        assert!(parse_status_callback(&form(&[("MessageStatus", "sent")])).is_err());
        assert!(parse_status_callback(&form(&[("MessageSid", "not-a-sid"), ("MessageStatus", "sent")])).is_err());
        assert!(parse_status_callback(&form(&[("MessageSid", sid)])).is_err());
    }

    const STATUS_URL: &str = "https://example.test/internal/twilio-status";

    #[test]
    fn status_callback_signature_is_checked_like_the_webhook() {
        let body = "MessageSid=SM0123456789abcdef0123456789abcdef&MessageStatus=delivered&ErrorCode=&AccountSid=ACtest";
        let sig = crate::twilio_signature("test-token", STATUS_URL, &crate::parse_form(body));
        assert!(crate::twilio_signature_ok("test-token", STATUS_URL, body, Some(&sig)));
        let parsed = parse_status_callback(&crate::parse_form(body)).unwrap();
        assert_eq!(parsed.status, Some("delivered"));
        // A forged status, another URL, another token, no token, no header: refused.
        let forged = body.replace("delivered", "read");
        assert!(!crate::twilio_signature_ok("test-token", STATUS_URL, &forged, Some(&sig)));
        assert!(!crate::twilio_signature_ok("test-token", "https://example.test/internal/twilio-webhook", body, Some(&sig)));
        assert!(!crate::twilio_signature_ok("other-token", STATUS_URL, body, Some(&sig)));
        assert!(!crate::twilio_signature_ok("", STATUS_URL, body, Some(&sig)));
        assert!(!crate::twilio_signature_ok("test-token", STATUS_URL, body, None));
    }

    #[test]
    fn status_callback_is_added_only_when_configured() {
        let base = "From=whatsapp%3A%2B15005550001&To=whatsapp%3A%2B15005550006&ContentSid=HX1".to_string();
        assert_eq!(with_status_callback(base.clone(), ""), base);
        assert_eq!(with_status_callback(base.clone(), "   "), base);
        let with = with_status_callback(base.clone(), STATUS_URL);
        let f = crate::parse_form(&with);
        assert_eq!(crate::form_value(&f, "StatusCallback"), Some(STATUS_URL));
        assert_eq!(crate::form_value(&f, "ContentSid"), Some("HX1"));
        let f = crate::parse_form(&with_status_callback(base, " https://example.test/internal/twilio-status?x=1&y=2 "));
        assert_eq!(crate::form_value(&f, "StatusCallback"), Some("https://example.test/internal/twilio-status?x=1&y=2"), "trimmed and encoded");
    }

    // --- heartbeat ---

    #[test]
    fn heartbeat_notifications_only_when_boolean() {
        assert_eq!(heartbeat_notifications_enabled(&json!({"process_id": "p", "notifications_enabled": false})), Some(false));
        assert_eq!(heartbeat_notifications_enabled(&json!({"process_id": "p"})), None, "old clients omit it");
        for v in [json!(null), json!("true"), json!(1), json!({})] {
            assert_eq!(heartbeat_notifications_enabled(&json!({"notifications_enabled": v})), None, "{v}");
        }
        assert_eq!(heartbeat_notifications_enabled(&json!([true])), None);
    }
}
