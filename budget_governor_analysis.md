# Mecris Budget Governor — Implementation State Report

*Generated 2025-07-08 from repo analysis*

---

## 1. Code Locations & Architecture

| Layer | Path | Role |
|-------|------|------|
| **Core logic (Python, legacy)** | `services/budget_governor.py` | Reference implementation with `BudgetGovernor` class; file-level deprecation notice points to WASM |
| **WASM component (Phase 1.7.2)** | `poc/wasm/budget-governor-py/app.py` | Spin component (`componentize-py` + `spin_sdk`); HTTP trigger `/internal/budget-governor`; KV persist + Variables config |
| **Virtual Budget Manager (Neon-backed)** | `virtual_budget_manager.py` | Multi-provider cost estimation + daily/monthly budgets; Postgres-backed via Neon; separate from envelope logic |
| **Usage Tracker (local Claude tracking)** | `usage_tracker.py` | Session recording, budget updates, Neon `budget_tracking` table; `$24.96` default period budget |
| **Billing Reconciliation** | `billing_reconciliation.py` | Drift correction between estimated vs. actual provider bills (Anthropic Admin API, Groq scraper) |
| **Groq Odometer** | `groq_odometer_tracker.py` | Monthly cumulative reading tracker with reset detection |
| **MCP Server integration** | `mcp_server.py` | Instantiates `_BudgetGovernor(spend_log_path="mecris_spend_log.json")`; exposes `get_budget_status`, `record_usage_session`, `get_real_anthropic_usage` tools; `_record_governor_spend()` routes by model name |
| **Tests** | `tests/test_budget_governor.py`, `tests/test_budget_governor_py_component.py`, `tests/test_virtual_budget_manager.py` | Full TDG coverage for envelope, routing, persistence, gate |

**No Rust/JS budget code exists** — pure Python + WASM component.

---

## 2. Bucket Configuration (5%/5% Envelope)

**Defaults** (env-overridable):

| Bucket | Type | Limit | Env Var | Description |
|--------|------|-------|---------|-------------|
| `helix` | SPEND | $100.00 | `HELIX_CREDIT_LIMIT` | Helix SaaS credits (use-it-or-lose-it) |
| `gemini` | SPEND | $50.00 | `GEMINI_FREE_LIMIT` | Gemini free-tier credits |
| `anthropic_api` | GUARD | $20.89 | `ANTHROPIC_BUDGET_LIMIT` | Anthropic paid API (ration carefully) |
| `groq` | GUARD | $10.00 | `GROQ_BUDGET_LIMIT` | Groq API (ration carefully) |

**Envelope constants** (both implementations):
- `DAYLIGHT_MINUTES = 780` (13h)
- `WINDOW_MINUTES = 39` (5% of 780)
- `ENVELOPE_SPEND_PCT = 5%` of period quota per rolling window

**Routing policy (Helix Inversion)**:
1. Prefer SPEND buckets with remaining quota (Helix → Gemini)
2. Fall back to least-used GUARD bucket
3. Emergency: least-exhausted GUARD even if over

---

## 3. Envelope Enforcement — Key Functions

### `check_envelope(bucket, cost_estimate) → "allow" | "defer" | "deny"`
- **deny**: `total_spent >= limit` (hard stop)
- **defer**: `window_spent_39min + cost_estimate > 0.05 × limit` (soft throttle)
- **allow**: otherwise

### `budget_gate(bucket, cost_estimate) → None | dict`
Used by MCP handlers as a pre-flight guard:
- Returns `None` → proceed
- Returns `{"budget_halted": true, ...}` on **deny** (blocking)
- Returns `{"budget_halted": false, "warning": ..., "envelope": "defer"}` on **defer** (non-blocking warning)

### Window calculation (`_window_spent`)
```python
cutoff = now_utc - timedelta(minutes=39)
sum(e["cost"] for e in log if e["bucket"] == bucket and e["ts"] >= cutoff)
```
Persisted to `mecris_spend_log.json` (local) or Spin KV (WASM).

---

## 4. MCP Budget-Monitor Tool Status

| Tool | Schema | Implemented? | Notes |
|------|--------|--------------|-------|
| `get_budget_status` | `user_id? → Dict` | ✅ | Returns `UsageTracker.get_budget_status()` — Neon `budget_tracking` table; **does not** expose envelope state |
| `record_usage_session` | `input_tokens, output_tokens, model?, session_type?, notes?, user_id? → Dict` | ✅ | Routes spend to `_budget_governor.record_spend(bucket, cost)` via `_record_governor_spend()` |
| `get_real_anthropic_usage` | `days? → Dict` | ✅ | Calls `AnthropicCostTracker` (Admin API); **guarded by `budget_gate("anthropic_api")`** |
| `get_narrator_context` | `user_id? → Dict` | ✅ | Embeds `_budget_governor.get_narrator_summary()` → `{routing_recommendation, envelope_status}` |
| **Dedicated envelope tools** | — | ❌ | No `budget_governor.check`, `budget_governor.status`, `budget_governor.gate` exposed via MCP |

**Sample `get_narrator_context` envelope excerpt:**
```json
"budget_governor": {
  "routing_recommendation": "helix",
  "envelope_status": "OK"
}
```

---

## 5. Phase Tracker (from issues #26, #29, #31, #214, #262)

| Phase | Scope | Status | Blockers |
|-------|-------|--------|----------|
| **1. Data Layer** | Spend log persistence (JSON → Neon), bucket config in Variables | ✅ Local JSON (`mecris_spend_log.json`); ✅ WASM KV; ❌ **Neon-backed log not yet wired** | `services/budget_governor.py` still uses file; no Neon migration script |
| **2. MCP Exposure** | Expose `check_envelope`, `get_status`, `budget_gate` as MCP tools | ❌ **Not started** | Only `get_narrator_context` surfaces envelope summary |
| **3. Bot Routing** | Autonomous agents call `budget_gate` before spend | ❌ **Design only** | `_record_governor_spend()` is post-hoc; no pre-flight in `record_usage_session` |
| **4. Helix Live Balance** | Periodic `/api/v1/me` poll → inject into status | ✅ Implemented in both implementations (best-effort, cached) | Requires `ANTHROPIC_BASE_URL` + `ANTHROPIC_API_KEY` pointed at Helix |

**Open TODOs (grepped from code):**
- `services/budget_governor.py:1` — "DEPRECATED LEGACY FILE … single source of truth is now the WASM component"
- `poc/wasm/budget-governor-py/app.py:13` — "Phase 1.7.2 / kingdonb/mecris#214"
- `mcp_server.py:1165` — `_record_governor_spend` only triggers **after** recording; no pre-check
- No Neon table `budget_spend_log` exists in `UsageTracker.init_database()`

---

## 6. Current Consumption & Projections

**No live spend log exists** (`mecris_spend_log.json` absent). Neon `usage_sessions` table is the source of truth for Claude costs.

| Bucket | Configured Limit | Est. Spend (from context) | Remaining | Days Left @ Current Burn |
|--------|------------------|---------------------------|-----------|--------------------------|
| **Claude (Anthropic API)** | $20.89 / period | ~$20.92 spent (per user prompt) | **−$0.03** (over) | **OVER** — `budget_gate` returns `deny` |
| **OpenRouter** | Not a bucket | $10/mo (per user prompt) | — | — |
| **Helix** | $100.00 | ~$400 credits available (per user prompt) | ~$400 | N/A (credits, not dollars) |
| **Gemini** | $50.00 | ~$20 free tier (per user prompt) | ~$30 | N/A |
| **Groq** | $10.00 | Minimal (odometer tracks monthly cumulative) | ~$10 | — |

**Usage Tracker budget status** (from `get_budget_status`):
- Period: 2025-08-06 → 2025-09-30 (~55 days)
- Total budget: $24.96 (default in `UsageTracker.init_database()`)
- Current remaining: **unknown without live Neon query** — run `mcp_reconcile_budget.py 19.54 24.96` to sync

**Burn rate**: `UsageTracker` computes `daily_burn_rate = 7-day-spend / 7`; projects `daily_burn_rate × days_remaining`. Alerts: `LOW_BUDGET` (<$5), `BURN_RATE_HIGH`, `PERIOD_ENDING`, `DAILY_LIMIT_EXCEEDED` (>$2/day).

---

## 7. Immediate Next Steps

1. **Wire Neon spend log** — Add `budget_spend_log` table + migrate `BudgetGovernor._persist_spend_log()` to Neon (Phase 1 completion)
2. **Expose envelope tools** — Add `budget_governor_check`, `budget_governor_status`, `budget_governor_gate` to `mcp_server.py` (Phase 2)
3. **Pre-flight gate in `record_usage_session`** — Call `budget_gate(bucket, est_cost)` **before** recording; return `deny` response if halted (Phase 3)
4. **Sync Anthropic console** — Run `python mcp_reconcile_budget.py <remaining> <total>` to align `UsageTracker` with reality
5. **Verify Helix balance** — Set `ANTHROPIC_BASE_URL=https://api.helixml.tech` + `ANTHROPIC_API_KEY`; confirm `get_helix_balance()` returns live credits

---

*Report covers code as of commit HEAD. Run `/mecris-orient` for live system health.*