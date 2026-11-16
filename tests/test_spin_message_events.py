"""Phase 1 of docs/WALK_REMINDERS.md (#363): see what happens to every reminder.

contracts/message_events.json is the source of truth. Live: needs the CI Spin service
(see spin_e2e.py) with scripts/migrate_v10_message_events.py applied. CI's Twilio token
cannot be decrypted, so every status callback there is refused: that is the case tested.
"""
import json

from spin_e2e import ROOT, cleanup_user, connect, http_json, make_user, refusal_count, requires_spin

CONTRACT = json.loads((ROOT / "contracts" / "message_events.json").read_text())
REF = "3f2b8c1e-7a4d-4e0b-9c55-2b1f0d6a9e11"


def _bearer(uid):
    return {"Authorization": f"Bearer TestUser {uid}", "Content-Type": "application/json"}


def _post(path, uid, body):
    return http_json("POST", path, headers=_bearer(uid), body=json.dumps(body))


def _nags(cur, uid):
    cur.execute("SELECT client_ref, status, channel, content FROM message_log WHERE user_id = %s ORDER BY id", (uid,))
    return cur.fetchall()


@requires_spin
def test_log_message_with_client_ref_is_idempotent():
    uid = "e2e-events-logref"
    conn = connect()
    cur = conn.cursor()
    try:
        make_user(cur, uid)
        body = dict(CONTRACT["api"]["log_message"]["request_example"])
        status, resp, text = _post("/internal/log-message", uid, body)
        assert status == 201, text
        assert resp == CONTRACT["api"]["log_message"]["response_201_example"]
        status, resp, text = _post("/internal/log-message", uid, body)
        assert status == 200, text
        assert resp == CONTRACT["api"]["log_message"]["response_200_duplicate_example"]
        assert _nags(cur, uid) == [(REF, "shown", "android_native", None)]

        status, resp, text = _post("/internal/log-message", uid, {"type": "walk_reminder", "client_ref": "not a ref"})
        assert status == 400, text
        assert resp["status"] == "error"
        assert len(_nags(cur, uid)) == 1, "a bad client_ref writes nothing"

        # Old clients omit client_ref: every post is a new nag, as before.
        for _ in range(2):
            status, _, text = _post("/internal/log-message", uid, {"type": "walk_reminder"})
            assert status == 201, text
        assert [r[0] for r in _nags(cur, uid)] == [REF, None, None]
    finally:
        cleanup_user(cur, uid)
        conn.close()


@requires_spin
def test_log_message_event_follows_the_contract():
    uid, other = "e2e-events-phone", "e2e-events-other"
    conn = connect()
    cur = conn.cursor()
    try:
        make_user(cur, uid)
        make_user(cur, other)
        status, _, text = _post("/internal/log-message", uid, {"type": "walk_reminder", "client_ref": REF})
        assert status == 201, text

        status, resp, text = _post("/internal/log-message-event", uid, {"client_ref": REF, "event": "tapped"})
        assert status == 201, text
        assert resp == CONTRACT["api"]["log_message_event"]["response_201_example"]

        cur.execute("SELECT to_char(now() AT TIME ZONE 'UTC' - interval '5 minutes', 'YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\"')")
        at = cur.fetchone()[0]
        event = {"client_ref": REF, "event": "action_later", "at": at}
        status, _, text = _post("/internal/log-message-event", uid, event)
        assert status == 201, text
        status, resp, text = _post("/internal/log-message-event", uid, event)
        assert status == 200, f"a retried upload is recorded once: {text}"
        assert resp["status"] == "success"

        cur.execute("""SELECT e.event, e.user_id, to_char(e.at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
                       FROM message_events e JOIN message_log m ON m.id = e.message_log_id
                       WHERE m.user_id = %s AND m.client_ref = %s ORDER BY e.id""", (uid, REF))
        rows = cur.fetchall()
        assert [(r[0], r[1]) for r in rows] == [("tapped", uid), ("action_later", uid)]
        assert rows[1][2] == at, "the phone's time is kept exactly"

        # The user comes from the token: another user's nag is unknown, whatever the body says.
        status, resp, text = _post("/internal/log-message-event", other, {"client_ref": REF, "event": "dismissed", "user_id": uid})
        assert status == 404, text
        assert resp == CONTRACT["api"]["log_message_event"]["response_404_example"]
        status, _, text = _post("/internal/log-message-event", uid, {"client_ref": "no-such-nag", "event": "tapped"})
        assert status == 404, text
        for bad in ({"client_ref": REF, "event": "shown"}, {"client_ref": "bad ref", "event": "tapped"}, {"event": "tapped"}):
            status, resp, text = _post("/internal/log-message-event", uid, bad)
            assert status == 400, f"{bad}: {text}"
            assert resp["status"] == "error"
        status, _, _ = http_json("POST", "/internal/log-message-event", headers={"Content-Type": "application/json"}, body=json.dumps({"client_ref": REF, "event": "tapped"}))
        assert status == 401
        cur.execute("SELECT count(*) FROM message_events e JOIN message_log m ON m.id = e.message_log_id WHERE m.user_id IN (%s, %s)", (uid, other))
        assert cur.fetchone()[0] == 2
    finally:
        cleanup_user(cur, uid)
        cleanup_user(cur, other)
        conn.close()


@requires_spin
def test_heartbeat_stores_notifications_enabled_only_when_sent():
    uid = "e2e-events-heartbeat"
    conn = connect()
    cur = conn.cursor()
    try:
        make_user(cur, uid)
        base = {"process_id": "com.mecris.go", "role": "android_client"}
        status, _, text = _post("/heartbeat", uid, base)
        assert status == 200, text
        cur.execute("SELECT notifications_enabled, notifications_checked_at FROM users WHERE pocket_id_sub = %s", (uid,))
        assert cur.fetchone() == (None, None), "old clients change nothing"

        status, resp, text = _post("/heartbeat", uid, {**base, "notifications_enabled": False})
        assert status == 200, text
        assert set(resp) == {"status", "message"}, "the response shape is unchanged"
        cur.execute("SELECT notifications_enabled, notifications_checked_at IS NOT NULL FROM users WHERE pocket_id_sub = %s", (uid,))
        assert cur.fetchone() == (False, True)

        status, _, text = _post("/heartbeat", uid, {**base, "notifications_enabled": "yes"})
        assert status == 200, text
        cur.execute("SELECT notifications_enabled FROM users WHERE pocket_id_sub = %s", (uid,))
        assert cur.fetchone()[0] is False, "a non-boolean value is ignored"
    finally:
        cleanup_user(cur, uid)
        conn.close()


@requires_spin
def test_unsigned_status_callback_is_refused_counted_and_changes_nothing():
    uid = "e2e-events-status"
    sid = "SM0123456789abcdef0123456789abcdef"
    conn = connect()
    cur = conn.cursor()
    try:
        make_user(cur, uid)
        cur.execute("""INSERT INTO message_log (date, user_id, type, sent_at, status, channel, message_sid, delivery_status)
                       VALUES (CURRENT_DATE, %s, 'walk_reminder', now(), 'sent', 'whatsapp', %s, 'queued') RETURNING id""", (uid, sid))
        before = refusal_count(cur, "twilio-status", "bad_signature")
        form = f"MessageSid={sid}&MessageStatus=read&ErrorCode="
        for headers in ({}, {"X-Twilio-Signature": "bm90IGEgc2lnbmF0dXJl"}):
            status, _, _ = http_json("POST", "/internal/twilio-status", headers={"Content-Type": "application/x-www-form-urlencoded", **headers}, body=form)
            assert status == 403
        assert refusal_count(cur, "twilio-status", "bad_signature") == before + 2
        cur.execute("SELECT delivery_status, delivery_error FROM message_log WHERE message_sid = %s", (sid,))
        assert cur.fetchone() == ("queued", None)
        cur.execute("SELECT count(*) FROM message_events e JOIN message_log m ON m.id = e.message_log_id WHERE m.message_sid = %s", (sid,))
        assert cur.fetchone()[0] == 0
    finally:
        cleanup_user(cur, uid)
        conn.close()
