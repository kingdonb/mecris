"""message_log tells the truth about verification sends and inbound messages
(#369 webhook proof, #358 slice).

- request-phone-verification binds the requested number to the caller's row and
  answers with a {status, message} object Android can parse as SyncResponse;
- every verification send is logged as phone_verification, sent or failed, without content;
- confirm answers with objects too;
- an unsigned webhook is refused and counted.

Live: needs the CI Spin service (see spin_e2e.py). CI's Twilio secrets cannot send,
so a verification request there always fails at the send, which is the case tested.
"""
import json

from spin_e2e import cleanup_user, connect, familiar, http_json, internal_key, make_user, refusal_count, requires_spin

TEST_NUMBER = "+15005550006"  # Twilio's documented magic test number
OTHER_NUMBER = "+15005550009"  # another Twilio magic test number
ALL_DAY = {"time_window_start": 0, "time_window_end": 23, "max_messages_per_day": 3}


def _bearer(uid):
    return {"Authorization": f"Bearer TestUser {uid}", "Content-Type": "application/json"}


def _assert_status_object(body, text):
    assert isinstance(body, dict), f"Android parses a SyncResponse object, got: {text[:80]}"
    assert set(body) == {"status", "message"}, body


@requires_spin
def test_failed_verification_send_is_logged_and_answers_with_an_object():
    uid = "e2e-msglog-verify"
    conn = connect()
    cur = conn.cursor()
    try:
        make_user(cur, uid, phone_enc="", phone_verified=True, autonomous=False)
        status, body, text = http_json("POST", "/internal/request-phone-verification", headers=_bearer(uid), body=json.dumps({"phone_number": TEST_NUMBER}))
        assert status == 502, text
        _assert_status_object(body, text)
        assert body["status"] == "error"
        assert TEST_NUMBER not in text

        cur.execute("SELECT type, status, channel, content FROM message_log WHERE user_id = %s", (uid,))
        assert cur.fetchall() == [("phone_verification", "failed", "whatsapp", None)]
        cur.execute("SELECT phone_number_encrypted, phone_verified FROM users WHERE pocket_id_sub = %s", (uid,))
        enc, verified = cur.fetchone()
        assert enc and TEST_NUMBER not in enc and "5005550006" not in enc, "the requested number is stored, encrypted"
        assert verified is False, "a new number is unverified until confirmed"
        cur.execute("SELECT COUNT(*) FROM phone_verifications WHERE user_id = %s", (uid,))
        assert cur.fetchone()[0] == 1
    finally:
        cleanup_user(cur, uid)
        conn.close()


@requires_spin
def test_confirm_answers_with_objects():
    uid = "e2e-msglog-confirm"
    conn = connect()
    cur = conn.cursor()
    try:
        make_user(cur, uid, phone_enc="", phone_verified=False, autonomous=False)
        status, body, text = http_json("POST", "/internal/confirm-phone-verification", headers=_bearer(uid), body=json.dumps({"code": "123456"}))
        assert status == 400, text
        _assert_status_object(body, text)
        cur.execute("INSERT INTO phone_verifications (user_id, code_hash, expires_at) VALUES (%s, 'not-a-real-hash', now() + interval '10 minutes')", (uid,))
        status, body, text = http_json("POST", "/internal/confirm-phone-verification", headers=_bearer(uid), body=json.dumps({"code": "not-a-code"}))
        assert status == 400, text
        _assert_status_object(body, text)
        assert body["status"] == "error"
        cur.execute("SELECT phone_verified FROM users WHERE pocket_id_sub = %s", (uid,))
        assert cur.fetchone()[0] is False
    finally:
        cleanup_user(cur, uid)
        conn.close()


@requires_spin
def test_unsigned_webhook_is_refused_and_counted():
    conn = connect()
    cur = conn.cursor()
    try:
        before = refusal_count(cur, "twilio-webhook", "bad_signature")
        status, _, _ = http_json("POST", "/internal/twilio-webhook", headers={"Content-Type": "application/x-www-form-urlencoded"}, body=f"Body=YES&From=whatsapp%3A{TEST_NUMBER}")
        assert status == 403
        assert refusal_count(cur, "twilio-webhook", "bad_signature") == before + 1
        cur.execute("SELECT COUNT(*) FROM message_log WHERE type IN ('walk_ack', 'inbound') AND sent_at > now() - interval '1 minute'")
        assert cur.fetchone()[0] == 0, "a refused webhook writes no message row"
    finally:
        conn.close()


def _dry_run_reason(uid):
    status, body, text = http_json("GET", f"/internal/trigger-reminders?dry_run=1&key={internal_key()}")
    assert status == 200, text
    mine = [u for u in body["users"] if u.get("familiar_id") == familiar(uid)]
    assert len(mine) == 1, text[:200]
    return mine[0]["reason"]


@requires_spin
def test_saving_the_profile_with_the_same_number_keeps_it_verified():
    """Android's Save always sends phone_number; an unchanged number must not un-verify the
    phone, or a routine Save turns the cloud WhatsApp fallback off."""
    uid = "e2e-profile-same-number"
    conn = connect()
    cur = conn.cursor()
    try:
        make_user(cur, uid, phone_enc="", phone_verified=False, prefs=ALL_DAY)
        status, _, text = http_json("POST", "/profile", headers=_bearer(uid), body=json.dumps({"phone_number": TEST_NUMBER}))
        assert status == 200, text
        cur.execute("UPDATE users SET phone_verified = TRUE WHERE pocket_id_sub = %s", (uid,))
        cur.execute("INSERT INTO phone_verifications (user_id, code_hash, expires_at) VALUES (%s, 'pending', now() + interval '10 minutes')", (uid,))
        reason_before = _dry_run_reason(uid)
        assert reason_before != "phone_unverified"

        same = "+1 (500) 555-0006"  # the same number, formatted differently
        status, _, text = http_json("POST", "/profile", headers=_bearer(uid), body=json.dumps({"phone_number": same, "autonomous_sync_enabled": True}))
        assert status == 200, text
        cur.execute("SELECT phone_verified FROM users WHERE pocket_id_sub = %s", (uid,))
        assert cur.fetchone()[0] is True, "an unchanged number stays verified"
        cur.execute("SELECT COUNT(*) FROM phone_verifications WHERE user_id = %s", (uid,))
        assert cur.fetchone()[0] == 1, "an unchanged number keeps its pending code"
        assert _dry_run_reason(uid) == reason_before

        status, _, text = http_json("POST", "/profile", headers=_bearer(uid), body=json.dumps({"phone_number": OTHER_NUMBER}))
        assert status == 200, text
        cur.execute("SELECT phone_verified FROM users WHERE pocket_id_sub = %s", (uid,))
        assert cur.fetchone()[0] is False, "a new number is unverified until confirmed"
        cur.execute("SELECT COUNT(*) FROM phone_verifications WHERE user_id = %s", (uid,))
        assert cur.fetchone()[0] == 0, "a code sent to the old number cannot verify the new one"
        assert _dry_run_reason(uid) == "phone_unverified"
    finally:
        cleanup_user(cur, uid)
        conn.close()


@requires_spin
def test_verification_requests_are_throttled_before_the_number_changes():
    uid = "e2e-verify-throttle"
    conn = connect()
    cur = conn.cursor()
    log = "INSERT INTO message_log (user_id, type, sent_at, status, channel) VALUES (%s, 'phone_verification', now() - %s::INTERVAL, 'failed', 'whatsapp')"
    try:
        make_user(cur, uid, phone_verified=True, autonomous=False)
        cur.execute("SELECT phone_number_encrypted FROM users WHERE pocket_id_sub = %s", (uid,))
        enc_before = cur.fetchone()[0]

        cur.execute(log, (uid, "10 seconds"))
        status, body, text = http_json("POST", "/internal/request-phone-verification", headers=_bearer(uid), body=json.dumps({"phone_number": TEST_NUMBER}))
        assert status == 429, text
        _assert_status_object(body, text)
        assert body["status"] == "error"
        cur.execute("SELECT phone_number_encrypted, phone_verified FROM users WHERE pocket_id_sub = %s", (uid,))
        assert cur.fetchone() == (enc_before, True), "a refused request changes nothing"
        cur.execute("SELECT COUNT(*) FROM message_log WHERE user_id = %s", (uid,))
        assert cur.fetchone()[0] == 1, "a refused request sends nothing"

        # Five sends today, each over a minute old: the daily limit holds.
        cur.execute("DELETE FROM message_log WHERE user_id = %s", (uid,))
        for _ in range(5):
            cur.execute(log, (uid, "61 seconds"))
        status, body, text = http_json("POST", "/internal/request-phone-verification", headers=_bearer(uid), body=json.dumps({"phone_number": TEST_NUMBER}))
        assert status == 429, text
        cur.execute("SELECT COUNT(*) FROM message_log WHERE user_id = %s", (uid,))
        assert cur.fetchone()[0] == 5
    finally:
        cleanup_user(cur, uid)
        conn.close()
