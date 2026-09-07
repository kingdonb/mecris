---
type: Architecture
title: Narrator Context as Primary Agent Sensor
description: The narrator-context MCP response is the compact live situation report combining goals, budget, daily aggregate, system health, recommendations, and presence.
generated: { by: agent/gpt-5.6-sol, at: 2026-09-06T23:20:00Z }
sources:
  - resource: docs/NARRATOR_CONTEXT_ARCHITECTURE.md
  - resource: mcp_server.py
  - resource: .pi/extensions/mecris/index.ts
  - resource: decisions/2026-09-06-deterministic-status.md
---
concept_id: "architecture/narrator-context"

# Narrator Context

`get_narrator_context()` is the preferred live query after authentication. It resolves an omitted identity through the credentials manager and returns one payload containing `summary`, `urgent_items`, `beeminder_alerts`, `goal_runway`, `budget_status`, `recommendations`, `daily_walk_status`, `daily_aggregate_status`, `system_pulse`, `presence`, and `budget_governor`.

The payload is live operational state. Do not copy values such as budget days, process IDs, goal runway, or timestamps into durable architecture prose as current truth.

## What the fields actually contain

- `urgent_items`: plain strings generated from critical goals, budget thresholds, walk state, and other urgent integrations.
- `beeminder_alerts`: plain human-readable alert strings produced by Beeminder emergency detection.
- `goal_runway`: structured goal records including `slug`, `title`, `safebuf`, `runway`, `rate`, `runits`, and `derail_risk`.
- `recommendations`: plain human-readable strings. They do **not** contain structured `priority`, `action`, or `context` fields.
- `budget_status`: live budget totals, remaining days, period end, alerts, and `budget_health`.
- `budget_governor`: a separate summary containing routing and envelope status.
- `system_pulse`: scheduler process state (`running`, `is_leader`, `process_id`, `last_status`, `intent`, `last_error`).
- `daily_aggregate_status.system_pulse.modalities`: per-system health for the MCP server, Android client, Akamai Functions, and historical cloud roles.
- `presence`: the latest human/ghost activity record; `presence_status` is currently a string such as `active_human`.

## Interpretation

For a human-readable update, present explicit alerts and runway without inventing structure that is absent from the payload. A reasonable order is:

1. Critical or warning Beeminder alerts and the corresponding shortest runway.
2. Other `urgent_items`, such as a missing daily walk.
3. Daily aggregate progress.
4. Budget health and remaining period.
5. Remaining recommendation strings.

The richer `/mecris` path lets a model interpret this payload. The native Pi `/status` path deliberately bypasses the model and formats five deterministic lines. Its formatter prefers a critical runway, then a warning runway, and uses alerts or urgent items for the next action.

## FastMCP transport shape

Over MCP, FastMCP returns the tool payload under `structuredContent.result` and also includes a JSON text representation. Consumers must unwrap `result`. Reading `structuredContent` directly produces fallback values such as `unknown` and `?/?`; this caused the first deterministic `/status` implementation to lose all useful fields.

## Related Concepts

- [Deterministic Pi Status and Progressive Context](../decisions/2026-09-06-deterministic-status.md): Defines the two status paths and the transport fix.
- [Beeminder Emergency Response](../runbooks/beeminder-emergency.md): Uses alerts and runway when action is required.
- [Agent Session Bootstrap](../runbooks/agent-bootstrap.md): Documents authentication and recovery.
- [Daily Aggregate and Majesty Cake](daily-aggregate.md): Defines the three daily accountability components.
