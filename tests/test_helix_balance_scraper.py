"""Tests for task 588 lever C1b/C1c: helix_balance_scraper (all mocked, no live calls)."""
import asyncio
from datetime import datetime, timezone

import pytest

from scripts import helix_balance_scraper as scr


# ---------------------------------------------------------------------------
# C1c — compute_scalars (§5.1 merge)
# ---------------------------------------------------------------------------

NOW = datetime(2026, 9, 19, 15, 0, tzinfo=timezone.utc)
PERIOD_END = NOW.timestamp() + 28 * 86400  # Oct 17-ish


def scalars(**kw):
    base = dict(current_balance=499.0, start_of_day_balance=500.0, period_end_ts=PERIOD_END,
                now=NOW, grant=100.0, cap=5.0, floor=1.0)
    base.update(kw)
    return scr.compute_scalars(base.pop("current_balance"), base.pop("start_of_day_balance"),
                               base.pop("period_end_ts"), now=base.pop("now"), **base)


def test_normal_day_pump_pace_wins():
    # 28 days left -> pump 3.57 > road 1 -> allowance 3.57 (< cap, cap never binds)
    s = scalars(beeminder_required_today=1.0)
    assert s["burn_allowance"] == round(min(5.0, max(100 / 28, 1.0, 1.0)), 2)
    assert s["burned_today"] == 1.0
    assert not s["inflow"]


def test_road_pressure_wins_when_more_urgent():
    s = scalars(current_balance=500.0, start_of_day_balance=500.0,
                period_end_ts=NOW.timestamp() + 100 * 86400,  # pump pace ~1.0
                beeminder_required_today=2.0)
    assert s["burn_allowance"] == 2.0  # BM 2 beats pump ~1


def test_topup_day_cap_refuses_the_number():
    # Top-up day: road demands ~$100; cap refuses the NUMBER (allowance = ordinary 5)
    s = scalars(beeminder_required_today=100.0, current_balance=599.0,
                start_of_day_balance=499.0)
    assert s["burn_allowance"] == 5.0
    assert s["burned_today"] == 0.0  # inflow floored at 0...
    assert s["inflow"] is True       # ...and flagged, never absorbed

def test_no_bm_tempo_floor_is_one():
    s = scalars(current_balance=500.0, start_of_day_balance=500.0,
                period_end_ts=NOW.timestamp() + 100 * 86400, beeminder_required_today=None)
    assert s["burn_allowance"] == 1.0  # pump ~1.0 == floor 1.0

def test_unknown_balance_yields_unknown_velocity():
    s = scalars(current_balance=None, start_of_day_balance=None)
    assert s["live_balance"] is None
    assert s["burned_today"] is None


# ---------------------------------------------------------------------------
# C1b — sync: change-gated straight copy (§4 push contract)
# ---------------------------------------------------------------------------

class FakeBM:
    def __init__(self, fail_status=None):
        self.calls = []
        self.fail_status = fail_status

    async def add_datapoint(self, goal, value, comment="", requestid=None, daystamp=None):
        self.calls.append({"goal": goal, "value": value, "comment": comment,
                           "requestid": requestid})
        if self.fail_status:
            exc = Exception(f"Beeminder API call failed: {self.fail_status}")
            exc.status_code = self.fail_status
            raise exc
        return True

    async def get_goal_datapoints(self, goal, count=7):
        return [{"value": self.calls[-1]["value"], "comment": self.calls[-1]["comment"],
                 "daystamp": "20260919"}]


@pytest.fixture
def neon(monkeypatch):
    """In-memory Neon: rows list + last_ok + requests processed flag."""
    state = {"rows": [], "last_ok": None, "processed": 0, "pushed": []}

    async def to_thread_noop(fn, *a, **k):
        return fn(*a, **k)

    monkeypatch.setattr(asyncio, "to_thread", to_thread_noop)

    def fake_last_ok(user_id):
        return state["last_ok"]

    def fake_insert(user_id, *, day, balance, delta, source, fetch_status, inflow):
        row = {"id": len(state["rows"]) + 1, "day": day, "balance": balance,
               "delta": delta, "source": source, "fetch_status": fetch_status,
               "inflow": inflow, "pushed_value": None}
        state["rows"].append(row)
        if fetch_status == "ok":
            state["last_ok"] = {"ts": NOW, "day": day, "balance": balance,
                                "pushed_value": None}
        return row["id"]

    def fake_mark_pushed(row_id, value):
        state["pushed"].append((row_id, value))
        for r in state["rows"]:
            if r["id"] == row_id:
                r["pushed_value"] = value
        if state["last_ok"]:
            state["last_ok"]["pushed_value"] = value

    def fake_processed(user_id):
        state["processed"] += 1

    monkeypatch.setattr(scr, "_fetch_last_ok_row", fake_last_ok)
    monkeypatch.setattr(scr, "_insert_row", fake_insert)
    monkeypatch.setattr(scr, "_mark_pushed", fake_mark_pushed)
    monkeypatch.setattr(scr, "_mark_requests_processed", fake_processed)
    return state


def wallet(balance):
    return {"balance": balance, "subscription_current_period_end": PERIOD_END}


def run(monkeypatch, neon, balances, bm=None, **kw):
    """balances: list consumed per get_wallet call (None = fetch failure)."""
    seq = list(balances)

    def fake_get_wallet(force=False):
        return wallet(seq.pop(0)) if seq and seq[0] is not None else None

    monkeypatch.setattr("scripts.helix_billing.get_wallet", fake_get_wallet)
    bm = bm or FakeBM()
    result = asyncio.run(scr.sync_helix_balance_to_beeminder(
        "u@x.com", beeminder_client=bm, **kw))
    return result, bm


def test_first_reading_pushes_straight_copy(monkeypatch, neon):
    result, bm = run(monkeypatch, neon, [499.11])
    assert result["pushed"] is True
    assert bm.calls[0]["value"] == 499.11
    assert bm.calls[0]["goal"] == "helix-ml"
    assert "source=api" in bm.calls[0]["comment"]
    assert bm.calls[0]["requestid"].startswith("helix-balance-")
    assert neon["pushed"] == [(1, 499.11)]
    assert result["readback"]["value"] == 499.11


def test_unchanged_value_is_silence(monkeypatch, neon):
    run(monkeypatch, neon, [499.11])                     # first: pushes 499.11
    result, bm = run(monkeypatch, neon, [499.11])        # same value again
    assert result["pushed"] is False
    assert "unchanged" in result["reason"]
    assert bm.calls == []                                # second run pushed nothing
    assert len(neon["rows"]) == 2                        # reading still logged (R2)


def test_moved_value_pushes_new_datapoint_same_day(monkeypatch, neon):
    run(monkeypatch, neon, [499.11])
    result, bm = run(monkeypatch, neon, [498.20])
    assert result["pushed"] is True
    assert bm.calls[0]["value"] == 498.20
    assert result["delta"] == pytest.approx(-0.91)


def test_force_pushes_even_unchanged(monkeypatch, neon):
    run(monkeypatch, neon, [499.11])
    result, bm = run(monkeypatch, neon, [499.11], force=True)
    assert result["pushed"] is True and len(bm.calls) == 1


def test_fetch_failure_logs_row_and_pushes_nothing(monkeypatch, neon):
    result, bm = run(monkeypatch, neon, [None])
    assert result["ok"] is False and result["pushed"] is False
    assert bm.calls == []
    row = neon["rows"][0]
    assert row["fetch_status"] == "failed" and row["balance"] is None  # unknown ≠ $0


def test_dry_run_would_push(monkeypatch, neon):
    result, bm = run(monkeypatch, neon, [499.11], dry_run=True)
    assert result["pushed"] is False and "dry-run" in result["reason"]
    assert bm.calls == []


def test_requestid_422_counts_as_success(monkeypatch, neon):
    bm = FakeBM(fail_status=422)  # dedupe fired = already in (Rust twin semantics)
    result, _ = run(monkeypatch, neon, [499.11], bm=bm)
    assert result["pushed"] is True and "dedupe" in result["note"]
    assert neon["pushed"] == [(1, 499.11)]


def test_real_push_failure_marks_nothing(monkeypatch, neon):
    bm = FakeBM(fail_status=500)
    result, _ = run(monkeypatch, neon, [499.11], bm=bm)
    assert result["pushed"] is False and "push failed" in result["reason"]
    assert neon["pushed"] == []  # must retry later; row stays unpushed
