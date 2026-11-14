"""POST /internal/log-message records a local phone nag (#213).

- The PocketID bearer is required; the user comes from the token, never the body.
- Only walk_reminder, arabic_pressure and greek_reminder are accepted.
- The row is channel android_native, status 'shown', with no content.
- sent_at is kept only within the last 24 hours; otherwise the row is stamped now.
- These rows feed the reminder gates' 4-hour damping, not the WhatsApp daily cap.

Live: needs the CI Spin service (see spin_e2e.py). Never reads .env.
"""
import json
from datetime import datetime, timedelta, timezone

from spin_e2e import cleanup_user, connect, http_json, internal_key, make_user, requires_spin

ALL_DAY = {"time_window_start": 0, "time_window_end": 23, "max_messages_per_day": 1}


def _headers(uid=None):
    h = {"Content-Type": "application/json"}
    if uid:
        h["Authorization"] = f"Bearer TestUser {uid}"
    return h


def _post(uid, payload):
    return http_json("POST", "/internal/log-message", headers=_headers(uid), body=json.dumps(payload))


@requires_spin
def test_a_shown_nag_is_logged_without_content():
    uid = "e2e-logmsg"
    conn = connect()
    cur = conn.cursor()
    try:
        make_user(cur, uid, autonomous=False)
        sent = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
        status, body, text = _post(uid, {"type": "walk_reminder", "channel": "android_native", "sent_at": sent,
                                         "content": "do not store me", "user_id": "someone-else"})
        assert status == 201, text
        assert isinstance(body, dict), text
        cur.execute("""SELECT user_id, type, channel, status, content, error_msg,
                              FLOOR(EXTRACT(EPOCH FROM now() - sent_at) / 60)::BIGINT, date
                       FROM message_log WHERE user_id IN (%s, 'someone-else')""", (uid,))
        rows = cur.fetchall()
        assert len(rows) == 1, rows
        user_id, ty, channel, st, content, err, age, day = rows[0]
        assert (user_id, ty, channel, st, content, err) == (uid, "walk_reminder", "android_native", "shown", None, None)
        assert 9 <= age <= 11, "sent_at within 24 h is kept"
        assert day is not None
    finally:
        cleanup_user(cur, uid)
        conn.close()


@requires_spin
def test_without_a_bearer_it_is_refused():
    status, _, _ = http_json("POST", "/internal/log-message", headers=_headers(),
                             body=json.dumps({"type": "walk_reminder", "channel": "android_native"}))
    assert status == 401


@requires_spin
def test_unknown_types_are_refused_and_old_times_are_clamped():
    uid = "e2e-logmsg-types"
    conn = connect()
    cur = conn.cursor()
    try:
        make_user(cur, uid, autonomous=False)
        for ty in ("phone_verification", "walk_ack", "inbound"):
            status, _, text = _post(uid, {"type": ty, "channel": "android_native"})
            assert status == 400, (ty, text)
        old = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        status, _, text = _post(uid, {"type": "greek_reminder", "channel": "whatsapp", "sent_at": old})
        assert status == 201, text
        cur.execute("""SELECT type, channel, FLOOR(EXTRACT(EPOCH FROM now() - sent_at) / 60)::BIGINT
                       FROM message_log WHERE user_id = %s""", (uid,))
        rows = cur.fetchall()
        assert len(rows) == 1 and rows[0][:2] == ("greek_reminder", "android_native"), rows
        assert rows[0][2] <= 1, "a sent_at older than 24 h is stamped now"
    finally:
        cleanup_user(cur, uid)
        conn.close()


@requires_spin
def test_a_logged_nag_damps_cloud_reminders_but_does_not_fill_the_cap():
    uid = "e2e-logmsg-gates"
    conn = connect()
    cur = conn.cursor()
    try:
        make_user(cur, uid, prefs=ALL_DAY)
        status, _, text = _post(uid, {"type": "arabic_pressure", "channel": "android_native"})
        assert status == 201, text
        status, body, text = http_json("GET", f"/internal/trigger-reminders?dry_run=1&key={internal_key()}")
        assert status == 200, text
        mine = [u for u in body["users"] if u["familiar_id"] == "fam-" + uid]
        assert len(mine) == 1, body
        assert mine[0]["minutes_since_last_nag"] is not None and mine[0]["minutes_since_last_nag"] <= 1
        assert mine[0]["nags_today"] == 0, "a local nag never counts toward the WhatsApp cap"
        assert mine[0]["reason"] == "damped", mine[0]
    finally:
        cleanup_user(cur, uid)
        conn.close()
