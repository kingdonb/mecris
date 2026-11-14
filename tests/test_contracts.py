"""Shared contract tables under contracts/ (parity anchor for #344, #346, #349, #368).

These tests keep the tables well formed and self-consistent:
- every file has its required keys;
- the Claude plan cases match claude_plan_usage.derive_state / summarize;
- the pulse and damping cases agree with the rules written in contracts/README.md,
  checked by small reference evaluators below (test-only, not production code).
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import claude_plan_usage as cpu

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
NY = ZoneInfo("America/New_York")
FILES = [
    "pulse_roles.json",
    "claude_plan_cases.json",
    "nag_damping_cases.json",
    "spin_heartbeat_response.json",
    "spin_status_response.json",
    "spin_aggregate_status_full.json",
]


def load(name):
    return json.loads((CONTRACTS / name).read_text())


def ts(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# --- files ---------------------------------------------------------------------

@pytest.mark.parametrize("name", FILES)
def test_contract_file_is_json(name):
    assert isinstance(load(name), dict)


def test_readme_names_every_file():
    readme = (CONTRACTS / "README.md").read_text()
    for name in FILES:
        assert f"`{name}`" in readme


@pytest.mark.parametrize("name", FILES)
def test_no_phone_numbers(name):
    text = (CONTRACTS / name).read_text()
    assert not re.search(r"\+\d{7,}", text)


# --- pulse_roles.json ----------------------------------------------------------

def pulse_verdict(table, role, minutes):
    entry = table["roles"].get(role)
    if entry is None:
        unlisted = table["unlisted_roles"]
        if minutes >= unlisted["show_under"]:
            return {"visible": False}
        return {"visible": True, "display": role.replace("_", " ").upper(), "status": unlisted["status"]}
    if entry["lifecycle"] == "retired":
        return {"visible": False}
    if entry["lifecycle"] == "paused":
        return {"visible": True, "display": entry["display"], "status": "paused"}
    if minutes < entry["healthy_under"]:
        status = "healthy"
    elif minutes < entry["degraded_under"]:
        status = "degraded"
    else:
        status = "offline"
    return {"visible": True, "display": entry["display"], "status": status}


class TestPulseRoles:
    table = load("pulse_roles.json")

    def test_required_keys(self):
        assert {"version", "roles", "unlisted_roles", "cases"} <= set(self.table)
        for role, entry in self.table["roles"].items():
            assert {"display", "lifecycle"} <= set(entry), role
            assert entry["lifecycle"] in ("expected", "paused", "retired"), role
            if entry["lifecycle"] == "expected":
                assert entry["healthy_under"] < entry["degraded_under"], role

    def test_decided_limits(self):
        roles = self.table["roles"]
        assert (roles["android_client"]["healthy_under"], roles["android_client"]["degraded_under"]) == (90, 240)
        assert (roles["leader"]["healthy_under"], roles["leader"]["degraded_under"]) == (2, 5)
        assert (roles["akamai_functions"]["healthy_under"], roles["akamai_functions"]["degraded_under"]) == (135, 250)
        assert roles["active_ghost"]["lifecycle"] == "paused"
        assert roles["fermyon_cloud"]["lifecycle"] == "retired"
        assert roles["unknown_cloud"]["lifecycle"] == "retired"
        assert self.table["unlisted_roles"]["show_under"] == 24 * 60

    def test_android_boundaries_present(self):
        ages = {c["minutes"] for c in self.table["cases"] if c["role"] == "android_client"}
        assert {89, 90, 239, 240} <= ages

    @pytest.mark.parametrize("case", load("pulse_roles.json")["cases"],
                             ids=lambda c: f"{c['role']}@{c['minutes']}")
    def test_case_matches_rules(self, case):
        assert pulse_verdict(self.table, case["role"], case["minutes"]) == case["expect"]


# --- claude_plan_cases.json ----------------------------------------------------

CLAUDE_CASES = load("claude_plan_cases.json")["cases"]


class TestClaudePlanCases:
    def test_required_keys(self):
        names = set()
        for case in CLAUDE_CASES:
            assert {"name", "now", "reading", "expect"} <= set(case)
            assert {"state", "reason", "stale", "summary_line", "fresh_window_kinds"} <= set(case["expect"])
            names.add(case["name"])
        assert len(names) == len(CLAUDE_CASES)

    def test_states_covered(self):
        states = {c["expect"]["state"] for c in CLAUDE_CASES}
        assert states == {"available", "constrained", "exhausted", "unknown"}

    @pytest.mark.parametrize("case", CLAUDE_CASES, ids=lambda c: c["name"])
    def test_derive_state(self, case):
        derived = cpu.derive_state(case["reading"], ts(case["now"]))
        assert derived["state"] == case["expect"]["state"]
        assert derived["reason"] == case["expect"]["reason"]
        assert derived["stale"] == case["expect"]["stale"]
        assert [w["kind"] for w in derived["fresh_windows"]] == case["expect"]["fresh_window_kinds"]

    @pytest.mark.parametrize("case", CLAUDE_CASES, ids=lambda c: c["name"])
    def test_summarize(self, case):
        summary = cpu.summarize(case["reading"], ts(case["now"]))
        for key in ("state", "reason", "stale", "summary_line"):
            assert summary[key] == case["expect"][key], key


# --- nag_damping_cases.json ----------------------------------------------------

DAMPING = load("nag_damping_cases.json")


def resolve(case):
    inputs = dict(DAMPING["base"])
    inputs.update(case["given"])
    return inputs


def _counts_for_damping(row):
    if row["type"] == "phone_verification":
        return False
    if row["channel"] == "whatsapp":
        return row["status"] in ("sent", "failed")
    if row["channel"] == "android_native":
        return row["status"] == "shown"
    return False


def _counts_for_cap(row):
    return (row["type"] != "phone_verification" and row["channel"] == "whatsapp"
            and row["status"] in ("sent", "failed"))


def failing_gates(inputs):
    """Every gate the inputs trip, as (verdict, reason) pairs."""
    consts = DAMPING["constants"]
    defaults = consts["default_prefs"]
    now = ts(inputs["now"])
    local = now.astimezone(NY)
    prefs = inputs["prefs"]
    out = []
    if inputs["phone_verified"] is not True:
        out.append(("skip", "phone_unverified"))
    until = inputs["vacation_mode_until"]
    if prefs.get("vacation_mode") or (until and ts(until) > now):
        out.append(("skip", "vacation"))
    days = prefs.get("enabled_days")
    if days is not None and local.strftime("%a").lower() not in [d.lower() for d in days]:
        out.append(("skip", "day_disabled"))
    types = prefs.get("message_types")
    if types is not None and "walk_reminder" not in types:
        out.append(("skip", "type_disabled"))
    start = prefs.get("time_window_start", defaults["time_window_start"])
    end = prefs.get("time_window_end", defaults["time_window_end"])
    if not start <= local.hour <= end:
        out.append(("skip", "outside_window"))
    if inputs["walked_today"]:
        out.append(("skip", "walked_today"))
    standdown = inputs["reminder_standdown_minutes"]
    beat = inputs["phone_heartbeat_minutes"]
    if standdown > 0 and beat is not None and beat < standdown:
        out.append(("stand_down", "phone_active"))
    log = inputs["message_log"]
    ages = [int((now - ts(r["sent_at"])).total_seconds() // 60) for r in log if _counts_for_damping(r)]
    if any(0 <= age < consts["damping_minutes"] for age in ages):
        out.append(("skip", "damped"))
    cap = prefs.get("max_messages_per_day", defaults["max_messages_per_day"])
    today = [r for r in log if _counts_for_cap(r) and ts(r["sent_at"]).astimezone(NY).date() == local.date()]
    if len(today) >= cap:
        out.append(("skip", "daily_cap"))
    return out


class TestNagDampingCases:
    def test_required_keys(self):
        assert {"version", "constants", "verdicts", "reasons", "base", "cases"} <= set(DAMPING)
        assert DAMPING["constants"]["timezone"] == "America/New_York"
        assert DAMPING["constants"]["damping_minutes"] == 240
        assert DAMPING["constants"]["default_reminder_standdown_minutes"] == 240
        assert DAMPING["base"]["prefs"] == {"time_window_start": 14, "time_window_end": 17, "max_messages_per_day": 3}
        names = set()
        for case in DAMPING["cases"]:
            assert {"name", "tags", "given", "expect"} <= set(case)
            assert set(case["given"]) <= set(DAMPING["base"]), case["name"]
            assert case["expect"]["verdict"] in DAMPING["verdicts"]
            assert case["expect"]["reason"] in DAMPING["reasons"]
            names.add(case["name"])
        assert len(names) == len(DAMPING["cases"])

    def test_every_reason_is_exercised(self):
        assert {c["expect"]["reason"] for c in DAMPING["cases"]} == set(DAMPING["reasons"])

    @pytest.mark.parametrize("case", DAMPING["cases"], ids=lambda c: c["name"])
    def test_case_matches_rules(self, case):
        gates = failing_gates(resolve(case))
        assert len(gates) <= 1, f"case trips more than one gate: {gates}"
        got = gates[0] if gates else ("send", "eligible")
        assert got == (case["expect"]["verdict"], case["expect"]["reason"])

    def test_python_guard_cases_are_otherwise_eligible(self):
        guard = [c for c in DAMPING["cases"] if {"damping", "daily_cap"} & set(c["tags"])]
        assert guard
        for case in guard:
            others = [g for g in failing_gates(resolve(case)) if g[1] not in ("damped", "daily_cap")]
            assert others == [], case["name"]


# --- Spin response fixtures ----------------------------------------------------

def test_spin_heartbeat_response():
    body = load("spin_heartbeat_response.json")
    assert set(body) == {"status", "message"}
    assert "mcp_server_active" not in body  # Spin never sends it; Android must read null


def test_spin_status_response():
    body = load("spin_status_response.json")
    assert set(body) == {"status", "message"}
    assert all(isinstance(v, str) for v in body.values())


class TestSpinAggregateStatusFull:
    body = load("spin_aggregate_status_full.json")

    def test_required_keys(self):
        assert {"score", "goals_met", "total_goals", "satisfied_count", "total_count", "all_clear",
                "components", "budget_remaining", "today_distance_miles", "today_steps",
                "vacation_mode_until", "phone_verified", "modalities", "system_pulse",
                "claude_plan", "pace"} <= set(self.body)
        assert set(self.body["components"]) == {"walk", "arabic", "greek"}

    def test_modalities(self):
        assert self.body["system_pulse"]["modalities"] == self.body["modalities"]
        for m in self.body["modalities"]:
            assert set(m) == {"role", "status", "last_seen", "minutes_since", "last_status"}

    def test_modalities_follow_pulse_roles(self):
        table = load("pulse_roles.json")
        by_display = {e["display"]: role for role, e in table["roles"].items()}
        for m in self.body["modalities"]:
            role = by_display[m["role"]]
            expect = pulse_verdict(table, role, m["minutes_since"])
            assert expect == {"visible": True, "display": m["role"], "status": m["status"]}

    def test_claude_plan_matches_python(self):
        plan = self.body["claude_plan"]
        assert {"state", "reason", "stale", "summary_line", "plan", "verified", "source",
                "observed_at", "age_minutes", "windows"} <= set(plan)
        for w in plan["windows"]:
            assert set(w) == {"kind", "pct_used", "resets_at", "fresh"}
        reading = {k: plan[k] for k in ("plan", "verified", "source", "observed_at")}
        reading["windows"] = [{k: w[k] for k in ("kind", "pct_used", "resets_at")} for w in plan["windows"]]
        now = ts(plan["observed_at"]).timestamp() + plan["age_minutes"] * 60
        summary = cpu.summarize(reading, datetime.fromtimestamp(now, tz=timezone.utc))
        for key in ("state", "reason", "stale", "summary_line"):
            assert summary[key] == plan[key], key

    def test_pace(self):
        assert self.body["pace"]
        for p in self.body["pace"]:
            assert set(p) == {"goal", "remaining", "per_hour", "clear_by", "due_today"}
