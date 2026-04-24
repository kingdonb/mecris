# The Observability Mandate: State over Streams

> **Mecris Strategic Mandate**  
> *Philosophy: "If you need a log to know what happened, your system is opaque. If your system is observable, the state tells the story."*

## 1. The "CloudWatch Lesson" (Anti-Pattern)
In large-scale production environments, unstructured, high-volume logging is a financial and cognitive liability.
*   **Cost**: In-excess of $100/day for a single account (CloudWatch) is a "hole" created by logging everything and reading nothing.
*   **Friction**: Searching "needles in a haystack" of log streams is an inferior debugging loop compared to inspecting structured state.

## 2. Event-First Observability (The Kubernetes Model)
Mecris adopts the Kubernetes model of observability: **Describe, don't grep.**
*   **State as Story**: The current state of the database should explain what the system is doing, what it last did, and why it failed.
*   **Events over Logs**: High-signal event records (like `kubectl get events`) are superior to unstructured stdout/stderr streams.
*   **The 4-Minute Rule**: If a system is in a degraded state, it should emit/update a structured event frequently enough that a "Describe" operation reveals the failure without needing to open a log viewer.

## 3. Implementation in Mecris

### A. The Heartbeat Evolution
Heartbeats in the `scheduler_election` table must transition from "I am alive" (timestamp only) to "I am doing X" (intent + status).
- **Current**: `last_heartbeat: 2026-04-24 02:43:50`
- **Mandate**: Add `last_status` and `last_error` fields. A heartbeat without a status is just a pulse; a heartbeat with a status is a report.

### B. The Action Log
The `message_log` and `autonomous_turns` tables are the primary observability tools. If the Akamai cloud decides to "stand down" and not send a message, that decision must be recorded as a structured **Event** in the database, not a line in `stdout`.

### C. The "Describe" Tool
The `get_system_health` and `get_narrator_context` MCP tools are the Mecris equivalent of `kubectl describe`. They must aggregate these structured events to provide a high-fidelity summary of system behavior.

## 4. Conclusion
We will not fail-closed because of a lack of logs. We will fail-open by ensuring that every "Silent Decision" (skipping a nag, choosing a model, yielding presence) leaves a permanent, queryable footprint in the Neon database. 

**Logs are for developers in a lab. State is for agents in the field.**
