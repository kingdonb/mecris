# Logic Vacuuming Candidates — Phase 0 Analysis

**Date**: 2026-03-29
**Epic**: kingdonb/mecris#154 (Logic Vacuuming — Migrate Accountability Brain to Rust/WASM)
**Author**: mecris-bot (yebyen/mecris#34)

---

## Overview

"Logic Vacuuming" is the strategic migration of accountability logic from the Python MCP server
into Rust/WASM components hosted by Spin. The goal: the system remains fully functional
(syncing, nagging, budgeting) even when the MCP server is offline.

This document analyses two prioritised candidates — **ReviewPump** and **BudgetGovernor** —
using the Vind-Box architectural blueprint. Per #154, migration proceeds in small, verifiable
increments managed by mecris-bot.

---

## Candidate 1: ReviewPump

**Source file**: `services/review_pump.py` (68 lines)

### What It Does

ReviewPump calculates the daily review target for a language-learning backlog.
Given the user's multiplier lever (1x–10x), the current debt, and tomorrow's liability,
it returns a target flow rate and a flow status (cavitation / laminar / turbulent).

Core logic:

```
target = tomorrow_liability + (current_debt / clearance_days)
```

The lever config table (`LEVER_CONFIG`) is static data: 8 entries mapping multipliers to
clearance windows (1–14 days). `ARABIC_POINTS_PER_CARD = 16` is a named constant.

### External Dependencies

| Dependency | Purpose | WASM treatment |
|---|---|---|
| `typing` (Python stdlib) | Type hints only | Drop (use Rust types) |
| None | — | — |

**ReviewPump has zero runtime external dependencies.** No network, no file I/O, no DB,
no clock. It is a pure function from integers to integers.

### Proposed WASM Interface (WIT sketch)

```wit
interface review-pump {
  // Lever multipliers are passed as tenths (10 = 1.0x, 20 = 2.0x, 100 = 10.0x)
  // to avoid floating-point ambiguity across WASM guests.
  record pump-status {
    multiplier-x10: u32,
    lever-name: string,
    target-flow-rate: s32,
    current-flow-rate: s32,
    status: string,       // "cavitation" | "laminar" | "turbulent"
    debt-remaining: s32,
    unit: string,         // "points" | "cards"
  }

  calculate-target: func(
    debt: s32,
    tomorrow-liability: s32,
    multiplier-x10: u32,
  ) -> s32;

  get-status: func(
    debt: s32,
    tomorrow-liability: s32,
    daily-completions: s32,
    multiplier-x10: u32,
    unit: string,
  ) -> pump-status;
}
```

No host imports required.

### Migration Assessment

| Attribute | Value |
|---|---|
| **Complexity** | LOW |
| **Host functions needed** | 0 |
| **Test coverage (Python)** | `tests/test_coaching_service.py` exercises it indirectly |
| **Blocking dependencies** | None |
| **Risk** | Minimal — pure arithmetic, static config table |

**Recommendation: Migrate ReviewPump first.** It is the simplest possible WASM component
(pure logic, no host bindings), which means it validates the end-to-end pipeline
(WIT definition → `cargo component build` → Spin component registration → Android host binding)
before any complex host integration is needed.

A standalone `mecris-go-spin/review-pump/` Spin component can be added to the existing
`spin.toml` as an HTTP route (`/internal/review-pump-status`) exercisable by the Android
app and the MCP server alike.

---

## Candidate 2: BudgetGovernor

**Source file**: `services/budget_governor.py` (366 lines)

### What It Does

BudgetGovernor enforces a 5%/5% rate envelope across four LLM spend buckets:

- **SPEND** (Helix, Gemini): use-it-or-lose-it credits — prefer these
- **GUARD** (Anthropic API, Groq): real money — ration carefully

The core rule: in any rolling 39-minute window (5% of a 13-hour daylight window),
no more than 5% of a bucket's period quota may be spent. Outputs: `allow`, `defer`, or `deny`.
A `budget_gate()` enforcement guard is wired into MCP handlers.

The spend log is persisted to a JSON file for cross-restart durability.
A live Helix balance is optionally fetched from the Helix API.

### External Dependencies

| Dependency | Purpose | WASM treatment |
|---|---|---|
| `datetime.utcnow()` | Rolling window cutoff | Host import: `host::now-ms() -> u64` |
| `os.getenv(...)` | Bucket limits and API keys | Host import: `host::get-var(name: string) -> option<string>` (already Spin `variables`) |
| File I/O (`spend_log_path`) | Spend log persistence | Host import: `host::read-spend-log() -> list<spend-event>` + `host::write-spend-log(...)` — OR use Spin KV store |
| `requests.get(...)` | Helix live balance | Host import: outbound HTTP (already `spin_sdk::http` outbound in Rust Spin) |
| `logging` | Diagnostics | Host import: `host::log(level: string, msg: string)` — or `eprintln!` in Rust |

**The core envelope logic is pure**: `check_envelope`, `_total_spent`, `_window_spent`,
`recommend_bucket`, `budget_gate` are all deterministic given a spend log snapshot and
the current timestamp. All impurity is confined to five well-defined host functions.

### Proposed WASM Interface (WIT sketch)

```wit
// Host provides these to the WASM component:
interface budget-governor-imports {
  now-ms: func() -> u64;
  read-spend-log: func() -> list<spend-event>;
  write-spend-log: func(log: list<spend-event>);
}

// WASM component exports these:
interface budget-governor {
  record spend-event {
    bucket: string,
    cost-cents: u64,  // store as integer cents to avoid float serialisation drift
    ts-ms: u64,
  }

  record bucket-status {
    bucket: string,
    bucket-type: string,    // "guard" | "spend"
    limit-cents: u64,
    spent-total-cents: u64,
    spent-window-cents: u64,
    remaining-cents: u64,
    envelope: string,       // "allow" | "defer" | "deny"
  }

  record gate-result {
    budget-halted: bool,
    warning: option<string>,
    bucket: string,
    envelope: string,
    routing-recommendation: string,
    message: option<string>,
  }

  check-envelope: func(bucket: string, cost-estimate-cents: u64) -> string;
  recommend-bucket: func() -> string;
  budget-gate: func(bucket: string, cost-estimate-cents: u64) -> option<gate-result>;
  get-status: func() -> list<bucket-status>;
}
```

For spend log persistence, using **Spin KV store** is cleaner than a custom
`read/write-spend-log` host pair — the Spin runtime already provides KV as a component
capability, with no bespoke host function needed.

### Migration Assessment

| Attribute | Value |
|---|---|
| **Complexity** | MEDIUM |
| **Host functions needed** | 2–3 (clock, KV store, outbound HTTP for Helix) |
| **Test coverage (Python)** | `tests/test_budget_governor.py` — 22 tests, strong |
| **Blocking dependencies** | Requires Spin KV store access in the component |
| **Risk** | Low-Medium — envelope math is simple; risk is in KV atomicity under concurrent requests |

**Recommendation: Migrate BudgetGovernor second**, after ReviewPump validates the pipeline.
The Spin KV store replaces the JSON file for the spend log. The Helix balance fetch uses
`spin_sdk::http` outbound (already present in `sync-service/src/lib.rs`). The clock
dependency is trivially fulfilled by `std::time::SystemTime` in Rust or
`spin_sdk::key_value` for coordinated time if needed.

The `budget_gate()` function is the highest-value export: once in WASM, every Spin
handler (sync-service, boris-fiona-walker, future Android via WASM runtime) gets
enforcement without depending on the Python MCP server being live.

---

## Candidate 3: Python-Native WASM via componentize-py (Phase 1.5 Path)

**Epic**: kingdonb/mecris#157 ("Holy Grail" — Python-in-WASM without Rust rewrite)
**Research date**: 2026-03-31 (yebyen/mecris#45)

### What is componentize-py?

`componentize-py` (BytecodeAlliance / Fermyon) compiles Python source into a WASM Component
by embedding a minimal CPython interpreter in the binary. It does **not** transpile Python
to Rust — it runs CPython inside WASM. The practical entry point for Spin is
`fermyon/spin-python-sdk`, which layers Spin-native bindings (KV store, outbound HTTP,
variables) on top of componentize-py.

### Key Limitations

| Feature | Support | Notes |
|---|---|---|
| `datetime`, `logging`, `os.getenv` | ✅ Works | WASI environment provides these |
| Pure Python (no C extensions) | ✅ Works | Core value proposition |
| `asyncio` event loop | ⚠️ PARTIAL | WASI async ≠ Python asyncio; top-level async handlers via WIT work, but internal `await` chains need refactoring at the component boundary |
| `psycopg2` (C extension) | ❌ BLOCKER | C extensions don't compile to WASM; replace with Neon HTTP API or WASI-native PG binding |
| `requests` library | ❌ Direct | Replace with `spin_sdk` outbound HTTP (already established pattern in Rust components) |
| Binary size | ⚠️ Large | CPython-in-WASM = 10–30 MB per component; material on Fermyon free tier |
| Threading | ❌ None | WASM is single-threaded |

### Python-Native Assessment per Existing Service

| Service | componentize-py Verdict | Blocker / Note |
|---|---|---|
| `services/review_pump.py` | **YES** | Pure arithmetic, no I/O, no async — trivially portable |
| `services/arabic_skip_counter.py` | **PARTIAL** | psycopg2 is the only blocker; replace with Neon HTTP API (`/sql` endpoint) and the logic is portable |
| `services/reminder_service.py` | **PARTIAL** | async/provider callback pattern needs WIT boundary refactor; Python logic preserved, asyncio event loop dropped in favour of sync WIT exports |
| `services/budget_governor.py` | **PARTIAL** | File I/O → Spin KV; `requests` → `spin_sdk` outbound HTTP; core envelope logic pure Python — all portable once I/O replaced |

### Recommended Approach

Use componentize-py as an **alternative path for Phase 1** (ReviewPump) and as
the default path for any future service migration before reaching for a Rust rewrite:

1. **ReviewPump (pure logic)**: Port as a Python component via `spin-python-sdk`.
   Avoids Rust entirely. Validates the componentize-py pipeline on this project.
2. **arabic_skip_counter**: Replace `psycopg2` with an HTTP call to Neon's HTTP API;
   wrap with componentize-py. Synchronous, small, testable.
3. **ReminderService / BudgetGovernor**: Boundary refactor only — make WIT exports
   synchronous wrappers; preserve all internal Python logic. The `asyncio` is a
   thin wrapper at the MCP layer, not intrinsic to the logic.

This is the spirit of kingdonb/mecris#157: **zero-rewrite migration** is achievable for
pure-logic and I/O-abstracted services. Only services with C extension runtime
dependencies (psycopg2) require I/O layer replacement — the Python *logic* is preserved.

---

## Recommended Migration Sequence

```
Phase 0  (now)       — This document. Candidates identified.
Phase 1  (next)      — Port ReviewPump as Python WASM via componentize-py/spin-python-sdk.
                        Alternative: port to Rust if Python binary size is prohibitive.
                        Expose as /internal/review-pump-status. Unit tests required.
Phase 1.5            — arabic_skip_counter: replace psycopg2 with Neon HTTP API,
                        wrap with componentize-py. Validates Python + I/O-via-HTTP pattern.
Phase 2              — Port BudgetGovernor core envelope (Python-native via componentize-py).
                        KV store spend log, outbound HTTP for Helix balance.
                        Python MCP server becomes a thin wrapper calling the WASM component.
Phase 3              — Android app binds WASM component directly (Wasmtime for Android).
                        MCP server is fully optional for these two subsystems.
```

---

## Implementation Notes

- **Existing Rust infrastructure**: `mecris-go-spin/sync-service/` uses `spin_sdk`, `spin_cron_sdk`,
  and `spin_sdk::pg`. New components follow the same pattern.
- **Blueprint**: `yebyen/useless` (frozen) is the structural reference for multi-host WASM Brain.
  Do not add Mecris logic to that repo.
- **Multiplier float encoding**: use integer tenths (10 = 1.0x) throughout the WIT interface
  to avoid IEEE 754 comparison hazards in the lever config table.
- **KV atomicity**: BudgetGovernor's spend log has an inherent race if two Spin instances
  process concurrent requests. For Phase 2, accept the race (spend log is advisory);
  add a CAS-style KV update in Phase 3 if needed.
- **Test strategy**: keep the Python tests (`tests/test_budget_governor.py`,
  `tests/test_coaching_service.py`) running against the Python shim throughout migration;
  add `#[test]` Rust unit tests in the WASM component crate.
