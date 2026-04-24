# Akamai Functions & Cron Evaluation

> **Mecris Strategic Document**  
> *Establishing a paper trail for the evaluation of Akamai Functions ($100/mo) vs. product value. This document serves as a baseline for the upcoming review with Stakeholders.*

## 📊 Current Status (2026-04-24)

### 1. Are Crons Firing?
**YES.**
*   **Verification**: The Neon database `scheduler_election` table shows a heartbeat for `akamai_functions` at `2026-04-24 02:43:50 UTC`. 
*   **Active Jobs**: `spin aka cron list` confirms three active schedules:
    *   `trigger-reminders`: Every 2 hours (`0 */2 * * *`)
    *   `failover-sync-edt/est`: Daily sync failover.
*   **Observability Strategy**: Per the **Observability Mandate**, we will not rely on `spin aka logs` for verification. Instead, we require the Akamai functions to record "Silent Decisions" (e.g., *Stand-down due to fresh Android heartbeat*) directly into the database as structured events.

### 2. Is it Providing Value?
**MARGINAL (FAILOVER ONLY).**
*   **The Findings**: In the last 3 days, **0 messages** have been sent via the Akamai cloud. 
*   **Interpretation**: 
    *   *Optimistic*: The system is working. The cloud is deferring to local heartbeats correctly.
    *   *Pessimistic*: The cloud might be failing to reach external APIs (e.g., Beeminder/Twilio) but heartbeating anyway.
*   **The Core Value Prop**: At $100/mo, Akamai is an insurance policy against your laptop being closed and your phone being dead simultaneously. 

## 🛠️ Evidence Log (State over Streams)

| Date | Event | Outcome | Source |
| :--- | :--- | :--- | :--- |
| 2026-04-24 | Heartbeat Check | Heartbeat found (02:43:50 UTC) | Neon DB `scheduler_election` |
| 2026-04-24 | Impact Audit | 0 messages sent in 72h | Neon DB `message_log` |

## ⚖️ Strategic Considerations

1.  **The "Ghost Nag" Insurance**: Is 100% failover reliability worth $1,200/year? If Mecris is a multi-tenant platform for paying users, it is a mandatory infrastructure cost.
2.  **State-First Visibility**: To justify the cost, the Akamai Function must become "self-describing." Every time it wakes up and *doesn't* send a message, it must log the reason in an `events` table.
3.  **WASM Purity**: Akamai is a pure-play WASM platform. Evaluating it is as much about supporting the WASM ecosystem as it is about the specific cron firing.

## 📝 Recommendations for next 7 days
1.  **Force an Akamai Fire**: Manually trigger the `/internal/trigger-reminders` endpoint while local servers are OFF and verify the outcome via `message_log`.
2.  **Implement Status Columns**: Expand the `scheduler_election` table to include `last_status` so we can see the cloud's intent without logs.
3.  **Cost-Benefit Analysis**: Compare the $100/mo cost against the actual number of "Critical Saves" (times the cloud sent a reminder when local devices were offline).
