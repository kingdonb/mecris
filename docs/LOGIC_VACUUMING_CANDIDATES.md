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

## Recommended Migration Sequence

```
Phase 0  (now)       — This document. Candidates identified.
Phase 1  (next)      — Port ReviewPump to Rust, expose as /internal/review-pump-status.
                        WIT interface, cargo component build, Spin registration, unit tests.
Phase 2              — Port BudgetGovernor core envelope to Rust.
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
