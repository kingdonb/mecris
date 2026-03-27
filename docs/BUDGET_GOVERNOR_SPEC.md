# Budget Governor Spec

*Tracking issue: kingdonb/mecris#144*

## Purpose

Extend Mecris cost metering to cover all active AI budget buckets with a unified rate envelope, routing logic, and inversion logic for "spend it" buckets.

## The 5%/5% Rate Envelope

In any **5% of the daylight window**, spend no more than **5% of any bucket's period quota**.

- Daylight window: 07:17–21:17 UTC (mecris-bot cron span) ≈ 13 hours
- 5% of window ≈ 39 minutes
- 5% of monthly quota ≈ 1.5 days' worth in one 39-minute slot

This smooths consumption across the full period. No binging, no starvation, every bucket survives to end of period.

## Budget Topology

| Bucket | Type | Period | Limit | Mode | Bot access |
|---|---|---|---|---|---|
| `anthropic_api` | Dollar credit | Expires EOY | $20.89 | GUARD (expiry) | No |
| `helix` | Dollar credit | Unknown expiry | $100.00 | SPEND (inverted) | Yes |
| `groq` | Dollar metered | Monthly | ~$20 comfort | GUARD (ceiling) | Yes |
| `copilot_work` | Premium requests | Monthly | Unknown cap | GUARD (critical) | No API |
| `copilot_cncf` | Premium requests | Monthly | Unknown cap | GUARD (critical) | No API |
| `gemini_personal` | Free tier | Daily + Monthly | Unknown cap | SPEND (use it) | Yes (CLI) |

## Two Modes

### GUARD mode
Goal: stay under the limit, survive to end of period.
Alert when consumed > 80% of period quota with > 20% of period remaining.
Hard stop when consumed > 95%.

### SPEND mode (inverted)
Goal: actively use the credit before it expires or is lost.
Alert when consumed < 20% of period quota with > 50% of period elapsed.
Encourage spending. Never ration.

`helix` and `gemini_personal` are SPEND buckets. Everything else is GUARD.

## Routing Logic

Before any expensive operation, the governor selects the best available bucket:

```
1. Is the operation within the 5%/5% envelope for the preferred bucket?
   - Yes → proceed on preferred bucket
   - No → check next bucket in preference order

2. Preference order (cheapest / most available first):
   gemini_personal → helix → groq → anthropic_api

3. Copilot is never routed programmatically — it's an IDE/CLI tool,
   not an API. Track it separately via honor system.

4. If all buckets are envelope-limited → defer to next 39-minute slot.
```

## Copilot Metering (No API)

GitHub does not expose Copilot premium request counts via API. Options:

- **Honor system**: bot opens a daily issue asking the human to report usage
- **Scraping**: parse the GitHub Copilot settings page (fragile, not recommended)
- **Manual tracking**: human updates a `data/copilot_usage.json` file the bot reads

Recommended for v1: manual `data/copilot_usage.json` with a schema the bot can read and update via prompt. Human updates it when they notice they're getting close.

Schema:
```json
{
  "copilot_work": {
    "period_start": "2026-03-01",
    "premium_requests_used": 0,
    "premium_requests_limit": 300,
    "last_updated": "2026-03-26"
  },
  "copilot_cncf": {
    "period_start": "2026-03-01",
    "premium_requests_used": 0,
    "premium_requests_limit": 300,
    "last_updated": "2026-03-26"
  }
}
```

## Gemini CLI Integration

`gemini --prompt "..."` is available and underused. The bot can invoke it for tasks that don't require full Claude capability. Check quota before invoking:

```bash
gemini --stats  # or equivalent — determine if machine-readable
```

If `--stats` is not machine-readable, parse the output heuristically or maintain a local counter in `data/gemini_usage.json`.

## Implementation Plan

### Phase 1 — Data layer
- `data/copilot_usage.json` — manual-update Copilot tracking
- `data/gemini_usage.json` — local counter for Gemini CLI calls
- Extend `usage_tracker.py` or new `budget_governor.py` with `BudgetGovernor` class
- `BudgetGovernor.check_envelope(bucket, cost_estimate)` → `allow | defer | deny`
- `BudgetGovernor.recommend_bucket(task_type)` → best available bucket

### Phase 2 — MCP exposure
- New `get_budget_governor_status` MCP tool
- Returns: per-bucket consumption %, envelope status, routing recommendation
- Fold into `/mecris-orient` output so the bot knows before it acts

### Phase 3 — Bot routing
- Bot uses governor recommendation in `/mecris-plan`
- Gemini CLI invoked for lightweight tasks (orient summaries, issue drafts)
- Helix used for heavier tasks (code review, pr-test analysis)
- Claude reserved for architecture decisions and novel problems

## Open Questions

- [ ] Is `gemini --stats` machine-readable? What does it return exactly?
- [ ] What is the actual Copilot premium request cap per seat per month?
- [ ] Can we hook Helix credit balance via `/api/v1/` — what endpoint?
- [ ] Should `BudgetGovernor` live in `usage_tracker.py` or a new file?
