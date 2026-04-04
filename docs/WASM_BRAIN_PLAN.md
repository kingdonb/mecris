# WASM-Brain: Strategic Migration Plan

This document tracks candidates for migration to WebAssembly (WASM) to enable "Submarine Mode" (offline or local-first execution) across Android, Spin, and CLI environments.

## Core Objective
Decouple core cognitive logic from the Python/Neon backend so it can run inside the Android app (via `componentize-py` or similar) or at the Edge (via Spin), ensuring the "Narator" and "Accountability Coach" remain alive even when the home server is offline.

## 1. Candidate Logic for WASM-Brain

| Logic Unit | Priority | Complexity | Rationale |
| :--- | :--- | :--- | :--- |
| **Nag Ladder (Tiers 1-3)** | High | Medium | Reminders must fire even if the central scheduler is down. |
| **Walk Heuristics** | High | Low | Android app needs to decide locally if a walk was "good" to provide immediate feedback. |
| **Budget Governor** | Medium | Low | Local sessions need to know their spend envelope without a round-trip to Neon. |
| **Language Velocity (Pump)** | Medium | High | Complex math involving Safebuf and Clozemaster stats. Hard to keep in sync. |
| **Narrator Recommendations** | Low | High | Requires broad system state (Beeminder, Groq, etc.). |

## 2. Shared Logic Implementation Strategy

### A. The "Common Core" Pattern
- Implement core heuristics in a language that compiles efficiently to WASM (Rust preferred, or strict Python for `componentize-py`).
- Use the **Wasmtime** or **Spin** runtime to host the component.
- **WIT (WebAssembly Interface Type)** definitions to ensure type safety across Kotlin (Android), Rust (Spin), and Python.

### B. Synchronization Challenges
- **State Gravity**: Neon is the source of truth. WASM-brain needs a local state cache (SQLite on Android, Key-Value store in Spin) and a robust reconciliation protocol.
- **Time Zones**: Everything must align on `US/Eastern` or UTC explicitly to prevent goal-met drift.

## 3. Near-Term Roadmap

- [ ] **Phase 1: Walk Heuristics (Rust)**: Port `WalkHeuristics` from Android Kotlin to Rust WASM. Share it with `boris-fiona-walker` Spin component.
- [ ] **Phase 2: Nag Ladder (Python/WASM)**: Use `componentize-py` to wrap `ReminderService` into a WASM component that can run in the background on Android.
- [ ] **Phase 3: WIT Definitions**: Formalize `AggregateStatus` and `ReminderRequest` in a shared `.wit` file.

## 4. Candidate Tracking (The "Fence" Check)

Current logic duplication needing synchronization:
- [x] `AggregateStatus` (Python vs Android Kotlin DTO) - **Status: Synchronized (Session 30)**
- [x] `Walk Completion Threshold` (Python 2000 steps vs Android 2000 steps) - **Status: Synchronized (Session 30)**
- [ ] `OIDC Scopes` (Python backend vs Android Kotlin) - **Status: Synchronized (Session 30)**

---
*Created: Saturday, April 4, 2026*
