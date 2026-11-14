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

from spin_e2e import cleanup_user, connect, http_json, make_user, refusal_count, requires_spin

TEST_NUMBER = "+15005550006"  # Twilio's documented magic test number


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
