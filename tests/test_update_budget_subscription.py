"""Subscription budget model (kingdonb/mecris#345).

- scripts/migrate_v9_subscription_budget.py adds source_type, plan and
  monthly_price_usd to budget_tracking. It is additive and running it twice is
  a no-op. Nothing here touches a live database.
- update_budget (tracker and MCP tool) accepts source_type, plan,
  monthly_price_usd, period_start and period_end; remaining_budget is optional.
- record_session never decrements a subscription row.
- _init_neon no longer seeds a fake $24.96 row.
- get_budget_status hands source_type and plan to evaluate_budget.
"""
import re
import sys
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

import usage_tracker as ut


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

class FakeSchema:
    """Just enough of Postgres to replay the migration's DDL twice."""

    def __init__(self):
        self.columns = {"id", "user_id", "total_budget", "remaining_budget",
                        "budget_period_start", "budget_period_end", "last_updated"}
        self.constraints = set()
        self.statements = []

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class FakeCursor:
    def __init__(self, schema):
        self.schema = schema

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def close(self):
        pass

    def execute(self, sql, params=None):
        self.schema.statements.append(sql)
        upper = sql.upper()
        for forbidden in ("DROP ", "DELETE ", "TRUNCATE ", "UPDATE "):
            assert forbidden not in upper, f"migration must be additive: {sql}"
        for col in re.findall(r"ADD COLUMN IF NOT EXISTS\s+(\w+)", sql, re.IGNORECASE):
            self.schema.columns.add(col.lower())
        bare = re.findall(r"ADD COLUMN\s+(?!IF NOT EXISTS)(\w+)", sql, re.IGNORECASE)
        for col in bare:
            if col.lower() in self.schema.columns:
                raise RuntimeError(f"column {col} already exists")
            self.schema.columns.add(col.lower())
        for name in re.findall(r"ADD CONSTRAINT\s+(\w+)", sql, re.IGNORECASE):
            guarded = "pg_constraint" in sql and "NOT EXISTS" in upper
            if name in self.schema.constraints and not guarded:
                raise RuntimeError(f"constraint {name} already exists")
            self.schema.constraints.add(name)


def _migration():
    sys.modules.pop("scripts.migrate_v9_subscription_budget", None)
    import scripts.migrate_v9_subscription_budget as mig
    return mig


def test_migration_adds_the_three_columns():
    schema = FakeSchema()
    _migration().migrate(schema)
    assert {"source_type", "plan", "monthly_price_usd"} <= schema.columns


def test_migration_twice_is_a_no_op():
    schema = FakeSchema()
    mig = _migration()
    mig.migrate(schema)
    after_first = (set(schema.columns), set(schema.constraints))
    mig.migrate(schema)
    assert (schema.columns, schema.constraints) == after_first


def test_migration_defaults_existing_rows_to_api_credit():
    sql = " ".join(_migration().STATEMENTS)
    assert re.search(r"source_type\s+TEXT\s+NOT NULL\s+DEFAULT\s+'api_credit'", sql, re.IGNORECASE)
    for value in ("api_credit", "subscription", "retired"):
        assert f"'{value}'" in sql


def test_migration_does_not_connect_on_import():
    with patch("psycopg2.connect") as connect:
        _migration()
    connect.assert_not_called()


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------

def _tracker_with_cursor(row=None, rowcount=1):
    tracker = ut.UsageTracker.__new__(ut.UsageTracker)
    tracker.neon_url = "postgres://fake"
    tracker.user_id = "test-user"
    tracker._use_neon = True
    tracker._db_initialized = True
    tracker.encryption = MagicMock(aesgcm=None)
    tracker.pricing = {"claude-3-5-sonnet-20241022": {"input": 3.0 / 1_000_000, "output": 15.0 / 1_000_000}}
    tracker.resolve_user_id = lambda user_id=None: user_id or "test-user"
    cur = MagicMock()
    cur.fetchone.return_value = row
    cur.rowcount = rowcount
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cur
    return tracker, conn, cur


_ROW = {"total_budget": 20.72, "remaining_budget": 20.72, "budget_period_start": "2026-11-13",
        "budget_period_end": "2027-05-13", "last_updated": "2026-11-14 20:00:00+00",
        "source_type": "subscription", "plan": "ultra", "monthly_price_usd": None}


def _executed(cur):
    return [(c.args[0], c.args[1] if len(c.args) > 1 else None) for c in cur.execute.call_args_list]


def test_update_budget_converts_to_subscription_without_dollars():
    tracker, conn, cur = _tracker_with_cursor(row=_ROW)
    with patch("psycopg2.connect", return_value=conn):
        result = tracker.update_budget(user_id="test-user", source_type="subscription", plan="ultra",
                                       period_start="2026-11-13", period_end="2027-05-13")
    update_sql, params = next((s, p) for s, p in _executed(cur) if s.lstrip().upper().startswith("UPDATE"))
    assert "source_type = %s" in update_sql and "plan = %s" in update_sql
    assert "budget_period_start = %s" in update_sql and "budget_period_end = %s" in update_sql
    assert "remaining_budget" not in update_sql
    assert "subscription" in params and "ultra" in params
    assert result["source_type"] == "subscription"
    assert result["plan"] == "ultra"
    assert result["remaining"] == 20.72


def test_update_budget_stores_monthly_price():
    tracker, conn, cur = _tracker_with_cursor(row={**_ROW, "monthly_price_usd": 200.0})
    with patch("psycopg2.connect", return_value=conn):
        result = tracker.update_budget(user_id="test-user", monthly_price_usd=200.0)
    update_sql, params = next((s, p) for s, p in _executed(cur) if s.lstrip().upper().startswith("UPDATE"))
    assert "monthly_price_usd = %s" in update_sql
    assert 200.0 in params
    assert result["monthly_price_usd"] == 200.0


def test_update_budget_still_takes_positional_dollars():
    tracker, conn, cur = _tracker_with_cursor(row={**_ROW, "source_type": "api_credit"})
    with patch("psycopg2.connect", return_value=conn):
        tracker.update_budget(15.5, 25.0, "2026-12-31", "test-user")
    update_sql, params = next((s, p) for s, p in _executed(cur) if s.lstrip().upper().startswith("UPDATE"))
    assert "remaining_budget = %s" in update_sql and "total_budget = %s" in update_sql
    assert {15.5, 25.0, "2026-12-31"} <= set(params)
    assert "source_type" not in update_sql


@pytest.mark.parametrize("kwargs", [
    {"source_type": "lifetime"},
    {"monthly_price_usd": -1.0},
    {},
])
def test_update_budget_rejects_bad_or_empty_input(kwargs):
    tracker, conn, cur = _tracker_with_cursor(row=_ROW)
    with patch("psycopg2.connect", return_value=conn):
        result = tracker.update_budget(user_id="test-user", **kwargs)
    assert "error" in result
    cur.execute.assert_not_called()


def test_record_session_never_decrements_a_subscription_row():
    tracker, conn, cur = _tracker_with_cursor()
    with patch("psycopg2.connect", return_value=conn):
        tracker.record_session("claude-3-5-sonnet-20241022", 1000, 1000, user_id="test-user")
    decrement = [s for s, _ in _executed(cur) if "remaining_budget = remaining_budget -" in s]
    assert decrement, "api_credit rows are still decremented"
    assert all("api_credit" in s and "source_type" in s for s in decrement)


def test_init_neon_seeds_no_fake_budget_row():
    tracker, conn, cur = _tracker_with_cursor(row=(0,))
    with patch("psycopg2.connect", return_value=conn):
        tracker._init_neon()
    for sql, _ in _executed(cur):
        assert "INSERT INTO budget_tracking" not in sql
        assert "24.96" not in sql


def test_get_budget_status_passes_source_type_and_plan():
    tracker, conn, cur = _tracker_with_cursor(row=dict(_ROW))
    cur.fetchone.side_effect = [dict(_ROW), {"sum": 0}, {"sum": 0}]
    with patch("psycopg2.connect", return_value=conn):
        status = tracker.get_budget_status("test-user")
    assert status["source_type"] == "subscription"
    assert status["plan"] == "ultra"
    assert status["budget_health"] in ("GOOD", "ENDING", "ENDED")
    assert status["period_expired"] is False
    assert isinstance(status["remaining_budget"], float)


def test_get_budget_status_without_the_column_is_api_credit():
    legacy = {k: v for k, v in _ROW.items() if k not in ("source_type", "plan", "monthly_price_usd")}
    legacy["budget_period_end"] = "2026-10-07"
    tracker, conn, cur = _tracker_with_cursor()
    cur.fetchone.side_effect = [legacy, {"sum": 0}, {"sum": 0}]
    with patch("psycopg2.connect", return_value=conn):
        status = tracker.get_budget_status("test-user")
    assert status["source_type"] == "api_credit"
    assert status["budget_health"] == "STALE"


# ---------------------------------------------------------------------------
# MCP tool
# ---------------------------------------------------------------------------

@pytest.fixture
def server():
    sys.modules.pop("mcp_server", None)
    with patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}), \
         patch("psycopg2.connect"):
        import mcp_server
        yield mcp_server
    sys.modules.pop("mcp_server", None)


def test_tool_accepts_subscription_fields_without_remaining_budget(server):
    with patch.object(server, "resolve_target_user", return_value="test-user"), \
         patch.object(server, "usage_tracker") as tracker:
        tracker.update_budget.return_value = {"source_type": "subscription"}
        result = server.update_budget(source_type="subscription", plan="ultra",
                                      period_start="2026-11-13", period_end="2027-05-13",
                                      monthly_price_usd=200.0)
    assert result == {"source_type": "subscription"}
    args, kwargs = tracker.update_budget.call_args
    assert args == (None, None, "2027-05-13", "test-user")
    assert kwargs == {"source_type": "subscription", "plan": "ultra",
                      "period_start": "2026-11-13", "monthly_price_usd": 200.0}


def test_tool_reports_a_missing_migration_as_an_error(server):
    with patch.object(server, "resolve_target_user", return_value="test-user"), \
         patch.object(server, "usage_tracker") as tracker:
        tracker.update_budget.side_effect = Exception('column "source_type" does not exist')
        result = server.update_budget(source_type="subscription")
    assert "migrate_v9_subscription_budget" in result["error"]


def test_tool_count_is_unchanged(server):
    import asyncio
    tools = asyncio.run(server.mcp.list_tools())
    assert len(tools) == 45
    schema = next(t for t in tools if t.name == "update_budget").inputSchema
    for field in ("source_type", "plan", "monthly_price_usd", "period_start", "period_end"):
        assert field in schema["properties"]
    assert "remaining_budget" not in schema.get("required", [])


@pytest.mark.asyncio
async def test_unified_cost_status_names_the_subscription(server):
    budget = {"source_type": "subscription", "plan": "ultra", "grant_end": "2027-05-13",
              "budget_health": "GOOD", "remaining_budget": 20.72, "days_to_grant_end": 180}
    groq = MagicMock()
    groq.check_reminder_needs.return_value = {}
    groq.get_usage_for_virtual_budget.return_value = {}
    plan = {"state": "available", "summary_line": "Claude: available (3% weekly, resets Mon 4:00 AM)"}
    with patch.object(server, "resolve_target_user", return_value="test-user"), \
         patch.object(server.usage_tracker, "get_budget_status", return_value=budget), \
         patch("groq_odometer_tracker._get_tracker", return_value=groq), \
         patch.object(server, "_get_claude_plan_status_sync", return_value=plan):
        result = await server.get_unified_cost_status()
    assert result["claude"]["source_type"] == "subscription"
    assert result["claude"]["summary"] == "Claude: Ultra until 2027-05-13, available (3% weekly, resets Mon 4:00 AM)"
    assert result["claude"]["plan_status"] == plan
