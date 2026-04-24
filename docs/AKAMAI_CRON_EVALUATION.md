# Akamai Functions & Cron Evaluation

> **Mecris Strategic Document**  
> *Establishing a paper trail for the evaluation of Akamai Functions ($100/mo) vs. product value. This document serves as a baseline for the upcoming review with Tim Enwall.*

## 📊 Current Status (2026-04-24)

### 1. Are Crons Firing?
**YES.**
*   **Verification**: The Neon database `scheduler_election` table shows a heartbeat for `akamai_functions` at `2026-04-24 02:43:50 UTC`. 
*   **Active Jobs**: `spin aka cron list` confirms three active schedules:
    *   `trigger-reminders`: Every 2 hours (`0 */2 * * *`)
    *   `failover-sync-edt/est`: Daily sync failover.
*   **Observability Gap**: `spin aka logs` currently reports "No logs found." This makes debugging *why* a cron may have failed or what it decided internally impossible without database-level side effects.

### 2. Is it Providing Value?
**MARGINAL (FAILOVER ONLY).**
*   **The Findings**: In the last 3 days, **0 messages** have been sent via the Akamai cloud. 
*   **Interpretation**: 
    *   *Optimistic*: The system is working perfectly. The Android app and local Python MCP server are heartbeating frequently enough that the cloud cron "stands down" as intended, saving SMS/WhatsApp costs.
    *   *Skeptical*: The cloud cron is heartbeating, but its internal logic might be failing silently or it lacks the data context to actually make a nagging decision.
*   **The Core Value Prop**: At $100/mo, Akamai is currently an insurance policy against your laptop being closed and your phone being dead simultaneously. 

## 🛠️ Evidence Log

| Date | Event | Outcome | Source |
| :--- | :--- | :--- | :--- |
| 2026-04-24 | Heartbeat Check | Heartbeat found (02:43:50 UTC) | Neon DB `scheduler_election` |
| 2026-04-24 | Log Inspection | "No logs found" | `spin aka logs` |
| 2026-04-24 | Impact Audit | 0 messages sent in 72h | Neon DB `message_log` |

## ⚖️ Strategic Considerations for Tim Enwall

1.  **The "Ghost Nag" Insurance**: Is 100% failover reliability worth $1,200/year? If Mecris is a personal project, probably not. If it is a multi-tenant platform for paying users, it is a mandatory infrastructure cost.
2.  **Infrastructure Weight**: Akamai Functions provide the "Global Brain" that doesn't sleep. However, we could achieve similar results with a $5/mo digital ocean droplet running the same Rust WASM logic. 
3.  **WASM Purity**: Akamai is a pure-play WASM platform. Evaluating it is as much about supporting the WASM ecosystem as it is about the specific cron firing.

## 📝 Recommendations for next 7 days
1.  **Force an Akamai Fire**: Manually trigger the `/internal/trigger-reminders` endpoint on Akamai while local servers are OFF to see if it actually sends a message.
2.  **Secure Logs**: Investigate why `spin aka logs` is empty. Without logs, the platform is "unsupportable" in production.
3.  **Cost-Benefit Analysis**: Compare the $100/mo cost against the actual number of "Critical Saves" (times the cloud sent a reminder when the human was about to derail and local devices were offline).
