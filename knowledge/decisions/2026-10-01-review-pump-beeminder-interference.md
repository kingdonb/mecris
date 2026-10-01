---
type: Decision
title: Review Pump Honors Beeminder Due-Today (0.1.2 Constructive Interference)
description: The review pump's remaining-today is max(pump quota, Beeminder due-today) and the goal is not met until the Beeminder derailing obligation is dispatched; operator rulings fix PLAY MODE intent, the NY-hardcoded goal day, and document Python/Rust drift fences for future tickets.
generated: { by: agent/zed, at: 2026-10-01T17:30:00Z }
stale_after: 2027-01-01
sources:
  - resource: services/beeminder_road.py
  - resource: mecris-go-spin/sync-service/src/lib.rs
  - resource: CHANGELOG.md
---

# Review Pump Honors Beeminder Due-Today

On 2026-10-01 a massive Clozemaster card dump (257 cards in the review stack)
coincided with the Beeminder `reviewstack` goal at safebuf 0 — "limit 86 today,
−171 today" — while the app showed REMAINING TODAY: 18. The interference rule
existed but its Beeminder side computed `-safebuf` (a count of safe DAYS, 0 on
beemergency day) instead of a card deficit, so it contributed nothing exactly
when it mattered.

## The Fix (0.1.2)

- The sync now reads `yaw`, `curval`, and `fullroad` from the goal JSON it
  already fetches, computes the road limit at the end of today, and stores
  `beeminder_road_today` + `beeminder_due_today` on `language_stats`
  (both twins: Rust edge and Python leader write the same columns).
- Interference at the REMAINING level: `remaining = max(pump_remaining, due)`;
  `quota = done + remaining` (stable as cards complete). Beeminder due is
  already net of completions — subtracting `daily_completions` again would
  double-count.
- `goal_met = pump_met AND due == 0` everywhere (languages, aggregate
  components, Python velocity/reminders).
- Pure math lives in `services/beeminder_road.py` (Python, executable spec)
  mirrored in Rust `sync-service::road_value_today` / `beeminder_due_today_value`
  / `effective_targets`; keep in lockstep.

## Operator Rulings (2026-10-01)

1. **PLAY MODE badge turning off when Beeminder dominates is intended.**
   Playing does not remove cards from the review stack; a derailing reviewstack
   goal demands removal — so it is not play mode.
2. **Timezone stays hardcoded America/New_York in source.** The system
   axiomatically has one user; that is their timezone. Per-user configurability
   is backlog-only and unlikely: a second user forks the codebase and
   self-deploys rather than sending Beeminder/other credentials to this
   service's database ("I am not their data overlord").
3. **Drift fences (documented, NOT fixed in 0.1.2 — Chesterton's fence: justify
   a thing's purpose before removing it):**
   - Greek 100-point min-target floor exists in Python/Kotlin, absent in Rust.
     Purpose hypothesis: a Moussaka-Hour daily baseline when backlog is zero.
     Operator was unaware of it and endorses Rust's omission (a 100-pt floor is
     near-unreachable under card-weight economics: a reviewed card at 100%
     known scores 16 pts, new cards <10). Future ticket may remove from Python
     using this documentation as justification.
   - Arabic `daily_completions` ÷ 16 at scrape time is canonical and
     intentional: 16 pts = a card reviewed at 100% known (four consecutive
     correct answers). The Python velocity `>500 → ÷16` guard is a defensive
     unit normalizer of uncertain provenance — leave as-is.
   - `mcp_server` still POSTs to the `/internal/review-pump-status-py` route
     that is commented out in `spin.toml` (Phase 1.7 Python-WASM pump
     experiment); harmless (local-pump fallback). Backlog: restore or delete.
4. **helix-ml guardrail:** the 0.1.0 budget governor is untouched by
   construction (no helix paths in the diff); post-deploy `check_witnesses.py`
   must show fresh `helix_balance_log` ok rows. A helix-ml widget in the app is
   a backlog item — the new columns are the seam for a generic due-today widget.
5. **WhatsApp reminders not received** (reported 2026-10-01): documentation
   only in 0.1.2 — pipeline map, ranked hypotheses (leader down > opt-out
   state > Twilio config > quiet gating), witness SQL, and `mecris nag
   eval`/`nag trigger` diagnostics live in the release-runbook of spec task
   000617 as the hand-off to a future ticket. Reminders fire only on the laptop
   leader (30-min job), so a dead leader is silent — a leader-freshness pulse
   is the candidate fix.
6. **Backlog (not funded in 0.1.2):** SpinKube / self-managed Kubernetes across
   the three availability zones and service-placement auto-negotiation (possibly
   out of Akamai Cloud — single-user system needs no global deployment);
   helix-ml widget; WhatsApp fix ticket; drift cleanups above.

## Related Concepts

- [Beeminder Integration](../architecture/beeminder-integration.md): The goal JSON fields (yaw, curval, fullroad, delta, safebuf) this fix depends on.
- [Budget Governor Service](../architecture/services/budget-governor.md): The helix-ml behavior explicitly untouched by this change (guardrail).
- [Go Services (mecris-go, mecris-go-spin, mecris-go-project)](../architecture/go-services.md): The Rust edge sync-service that computes and serves the effective targets.
