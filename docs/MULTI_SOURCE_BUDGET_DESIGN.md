# Multi‑Source Budget Aggregation Design

## Persistent Budget Model (SQLite)

| Table | Columns | Purpose |
|-------|---------|---------|
| `budget_cycle` | `id INTEGER PK`, `start_date DATE`, `end_date DATE`, `target_usd REAL`, `notes TEXT` | Defines a budgeting period (e.g., month). |
| `budget_source` | `id INTEGER PK`, `cycle_id INTEGER → budget_cycle.id`, `name TEXT`, `type TEXT` (`realtime|manual`), `currency TEXT`, `amount_usd REAL`, `last_updated TIMESTAMP`, `raw_payload TEXT` | Stores a single cost snapshot from a source. |
| `budget_discrepancy` | `id INTEGER PK`, `cycle_id INTEGER → budget_cycle.id`, `source_a_id INTEGER → budget_source.id`, `source_b_id INTEGER → budget_source.id`, `diff_usd REAL`, `percent_diff REAL`, `grade TEXT` (`EXCELLENT|GOOD|FAIR|POOR`), `analysis TEXT`, `generated_at TIMESTAMP` | Records pair‑wise comparison and grade. |

*Indices*: `budget_source(cycle_id, name)`, `budget_discrepancy(cycle_id)`.

## MCP Endpoint Changes

| Method & Path | Description | Request Body | Response |
|---------------|-------------|--------------|----------|
| `POST /budget/cycle` | Create a new budgeting period. | `{ "start_date":"YYYY‑MM‑DD", "end_date":"YYYY‑MM‑DD", "target_usd":float }` | `{ "cycle_id":int }` |
| `GET /budget/cycle/{id}` | Retrieve cycle metadata + aggregated totals. | – | `{ "cycle":{…}, "totals":{ "realtime_usd":float, "manual_usd":float, "overall_usd":float } }` |
| `POST /budget/source` | Upsert a cost snapshot for a cycle. | `{ "cycle_id":int, "name":string, "type":"realtime|manual", "currency":"USD", "amount_usd":float, "raw_payload":string (optional) }` | `{ "source_id":int }` |
| `GET /budget/discrepancy/{cycle_id}` | Compute and return discrepancy report for the cycle. | – | `{ "grade":"EXCELLENT", "diff_usd":float, "percent":float, "details":[ … ] }` |
| `POST /budget/reconcile` *(optional)* | Trigger async recompute of all discrepancies for a cycle. | `{ "cycle_id":int }` | `{ "status":"queued" }` |

All endpoints use existing auth tokens and are idempotent where appropriate.

## Data Ingestion Formats

| Source | Type | Expected Payload |
|--------|------|------------------|
| Claude / Anthropic API | `realtime` | `{ "used_credits":float, "cost_usd":float, "timestamp":ISO8601 }` |
| Groq API | `realtime` | `{ "project_id":string, "spent_usd":float, "timestamp":ISO8601 }` |
| Manual Dashboard Entry | `manual` | `{ "display_html":"<div…>$0.42 USD</div>", "extracted_usd":float, "recorded_at":ISO8601 }` |

Manual entries are submitted via `POST /budget/source`; the UI/CLI can prompt the user to paste the HTML snippet. A simple regex (`\$(\d+(\.\d+)?)\s*USD`) extracts the amount.

## Discrepancy Detection & Grading

1. **Pairwise Comparison** – For each `budget_cycle`, compare every `realtime` source against the `manual` source(s).
2. **Diff Calculation**
   ```python
   diff_usd = abs(realtime.amount_usd - manual.amount_usd)
   percent = diff_usd / max(realtime.amount_usd, manual.amount_usd) * 100
   ```
3. **Grade Assignment**
   | Percent Diff | Grade |
   |--------------|-------|
   | ≤ 1 % | EXCELLENT |
   | ≤ 5 % | GOOD |
   | ≤ 10 % | FAIR |
   | > 10 % | POOR |
4. **Analysis Text** – Auto‑generated summary (e.g., “Realtime source X is $Y (Z %) higher than manual entry; possible untracked usage or API‑key leakage.”).
5. Store the result in `budget_discrepancy` for later reporting.

## CLI / Monitor Integration

- **`mecris budget status [--cycle <id>]`** – Shows start/end dates, target, summed realtime & manual totals, overall variance, and grade.
- **`mecris budget add-source --cycle <id> --name <src> --type <realtime|manual> --amount <usd> [--raw <payload>]`** – Updates the SQLite `budget_source` table via the MCP endpoint.
- **`mecris budget alert --threshold <percent>`** – Polls the latest discrepancy; if `percent_diff` exceeds the threshold, emits a console warning and optionally triggers a Twilio alert via `/beeminder/alert`.

## Workflow Example
1. **Start Cycle** – `mecris budget cycle create --start 2025‑09‑01 --end 2025‑09‑30 --target 30`.
2. **Realtime Updates** – Background jobs call `POST /budget/source` after each Claude/Groq usage report.
3. **Manual Entry** – At month‑end, user copies the dashboard HTML snippet and runs:
   ```bash
   mecris budget add-source --cycle 3 \
       --name "Claude Dashboard" --type manual \
       --amount 0.42 --raw "<div…>$0.42 USD</div>"
   ```
4. **Reconcile** – `mecris budget reconcile --cycle 3` (or automatically on manual entry).
5. **Review** – `mecris budget status --cycle 3` shows totals, diff, and grade.

## Extensibility
- New sources only need a unique `name` and a POST to `/budget/source`.
- `raw_payload` preserves original data for audit.
- Grading thresholds can be adjusted via a future configuration endpoint.

## Security & Auditing
- All writes are authenticated with the existing MCP token model.
- `raw_payload` and `last_updated` provide full traceability.
- Manual entries are linked to the invoking user (captured in request context).

---

## Current Todo List (Status)

- **Extend SQLite schema for persistent budget cycles and source tracking** – *pending*
- **Design MCP endpoints: update source data, retrieve aggregated budget, get discrepancy report** – *pending*
- **Define data ingestion format for real‑time usage sources (Claude, Groq) and manual entry source** – *pending*
- **Specify discrepancy detection algorithm and grade calculation** – *pending*
- **Outline reporting CLI/monitor integration and alerting on drift** – *pending*
