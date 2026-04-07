# Feature Specification: The Nag Ladder (Escalation Engine)
**Status:** DRAFT
**Date:** 2026-04-07
**Feature ID:** CORE-002 (The Nag Ladder)

## 1. Intent
To define the pure logic of Mecris's notification escalation system (The Nag Ladder) as a host-agnostic WebAssembly (WASM) component. This component must deterministically calculate whether the user should be interrupted, and at what severity, based strictly on idle time, goal runway, and physiological context (e.g., sleep windows).

## 2. The WASM vs. Host Boundary
This specification explicitly delineates the boundary between the pure escalation logic (The Brain) and external reality (The Host).

### 2.1 The Host's Responsibility (I/O & Reality)
The host environments (Go Operator, Python MCP, etc.) are strictly responsible for side-effects and data gathering. The host MUST:
*   Fetch the user's current Beeminder goal runway (time until derailment).
*   Determine the user's last known interaction time (presence lock or message timestamp) to calculate `idle_hours`.
*   Provide the current UTC timestamp and the user's timezone.
*   Execute the actual SMS delivery via Twilio or WhatsApp, using the template indicated by the WASM output.

### 2.2 The Brain's Responsibility (Pure Calculation)
The WASM Brain takes a structured JSON input of current goal states, idle time, and the current clock time. It performs NO network calls and maintains NO internal state. It outputs a structured JSON response dictating if a message should be sent, its tier, and the required message template context.

## 3. Functional Requirements

### FR-001: The Escalation Engine Input
The Brain must accept a `NagRequest` JSON object containing:
*   `goals`: Array of objects `{ slug: String, is_completed: Boolean, runway_hours: Float }`
*   `idle_hours` (Float): Hours since the user last interacted with the system.
*   `current_hour_local` (Integer): The current hour (0-23) in the user's local timezone.
*   `global_cooldown_active` (Boolean): True if a message was sent very recently.

### FR-002: Notification Tiers
The engine must output a `NagResult` JSON object containing `should_send` (Boolean) and, if true, the `tier` (Integer) and `template_id` (String).

*   **Tier 1 (Gentle):** Routine reminders (e.g., afternoon dog walk reminder, Arabic review reminder). Triggered when a daily task is incomplete, the system is off cooldown, and it is during appropriate waking hours.
*   **Tier 2 (Escalated):** Triggered when a Tier 1 condition exists AND the user has been completely unresponsive (`idle_hours > 6.0`). The output `template_id` must shift to a fallback/escalated variant that demands an explicit response or action.
*   **Tier 3 (Emergency):** Triggered ONLY when a critical goal (Beeminder) drops below an emergency threshold (`runway_hours < 2.0`). This tier completely bypasses routine time-of-day checks and standard cooldowns.

### FR-003: Cooldown and Sleep Window Enforcement
*   **Sleep Window:** The engine must suppress all Tier 1 and Tier 2 messages between 22:00 and 07:00 local time.
*   **Emergency Override:** Tier 3 emergencies bypass the sleep window (the system *will* wake the user up to prevent a derailment).
*   **Global Cooldown:** If `global_cooldown_active` is true, Tier 1 and Tier 2 messages are suppressed to prevent spamming. Tier 3 messages may still fire depending on the strictness of the emergency.

## 4. Edge Cases

### EC-001: Exact Threshold Boundaries
If `runway_hours == 2.0` exactly, the system must NOT trigger Tier 3. Tier 3 requires strict `< 2.0` to avoid premature panic.
If `idle_hours == 6.0` exactly, the system remains in Tier 1. Tier 2 requires strictly `> 6.0`.

### EC-002: Multiple Triggers
If multiple goals require nagging, the system must prioritize the output: Tier 3 > Tier 2 > Tier 1. It only returns the single highest-priority nag directive to prevent message flooding.

## 5. Success Criteria

*   **SC-001 (Host Ignorance):** The WASM component compiles to `wasm32-unknown-unknown` (or `wasm32-wasip1`) and imports zero host functions for network or disk access.
*   **SC-002 (Deterministic Escalation):** Given a goal with 1.5 hours runway and `idle_hours = 7.0`, the system deterministically outputs Tier 3 (Emergency), prioritizing the runway over the idle escalation.
*   **SC-003 (Sleep Suppression):** Given an incomplete routine goal at 03:00 local time, the system outputs `should_send: false`, cleanly suppressing the nag.