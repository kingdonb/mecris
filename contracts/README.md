# contracts/

Shared truth tables for the Mecris arms (Python MCP, Spin sync-service, Android, web).
Every arm reads these files **in place**. Do not copy them into an arm.

| File | Owner (decides changes) | Readers |
|---|---|---|
| `pulse_roles.json` | Spin pulse (`mecris-go-spin/sync-service`) | Python pulse (`mcp_server.py`, `services/health_checker.py`), Android pulse card tests |
| `claude_plan_cases.json` | Python `claude_plan_usage.py` (reference implementation) | Spin `claude_plan.rs`, Android Claude plan card tests |
| `nag_damping_cases.json` | Spin reminder gates (`trigger-reminders`) | Python send guard (`mcp_server.py`, `twilio_sender.py`) |
| `spin_heartbeat_response.json` | Spin `POST /heartbeat` | Android `SpinContractTest` |
| `spin_status_response.json` | Spin `{status, message}` responses, including phone verification | Android `SpinContractTest` (as `SyncResponse`) |
| `spin_aggregate_status_full.json` | Spin `GET /aggregate-status?full=true` (v0.3.0 shape) | Android `SpinContractTest`, web dashboard |

`tests/test_contracts.py` checks every file's required keys, runs the Claude plan
cases through `claude_plan_usage`, and checks the pulse and damping cases against
the rules below so the tables cannot contradict themselves.

To change a value: edit the contract in its own commit, then make every reader's
tests pass. A case that one arm cannot meet is a parity bug (see the
`parity-arbitration` skill), not a reason to fork the table.

## Reading the files

- Python (repo root is the pytest root): `Path(__file__).resolve().parents[1] / "contracts" / NAME` from `tests/`.
- Rust, from `mecris-go-spin/sync-service/src/*.rs`, in `#[cfg(test)]` only:
  `include_str!("../../../contracts/NAME")`.
- Kotlin unit tests run with `mecris-go-project/app` as the working directory:
  `File("../../contracts/NAME")`.

Keys starting with `_doc` are comments. `version` changes when a field changes meaning.

## pulse_roles.json (#346)

`roles` maps a `scheduler_election.role` to its display name, lifecycle and limits.
For `expected` roles the status is `healthy` while `minutes_since < healthy_under`,
`degraded` while `< degraded_under`, otherwise `offline`.

- `android_client`: healthy under 90 min, degraded under 240 (was 20/60 when the worker ran every 15 min).
- `leader` 2/5 and `akamai_functions` 135/250: unchanged.
- `active_ghost`: `paused`, shown once whatever its age, while the ghost is off (#359).
- `fermyon_cloud`, `unknown_cloud`: `retired`, never shown.
- Any other role (including the stray `unknown`): status `unknown`, shown only while under 24 h old.

`cases` give a role and an age with the expected `{visible, display, status}`.

Each role is shown at most once. Readers select `user_id = $1 OR user_id IS NULL`, so one role
can have several rows (`UNIQUE (user_id, role)` allows many NULL-user rows). The row with the
newest heartbeat wins; on an equal heartbeat the user's own row wins. Visibility and status
come from the winning row alone. `duplicate_cases` pin this.

Carry-over: the web types (`web/src/types/mecris.ts`) and `Dashboard.css` have no `paused`
status yet, so whichever arm owns the web must add it before the GHOST row renders styled.

## claude_plan_cases.json (#344)

Each case is a reading (or `null`) plus `now`; `expect` holds `state`, `reason`,
`stale`, `summary_line` and `fresh_window_kinds`, exactly as
`claude_plan_usage.derive_state` / `summarize` produce them today.

A reading has two writers, and readers must accept both shapes:

| | manual (`record_claude_plan_usage`) | status line (`source = claude_code_cli`, #383) |
|---|---|---|
| `pct_used` | a number, usually whole (`23.0`) | a number, often fractional (`26.0`, `23.5`) |
| `resets_at` | `-05:00` offset (`2026-11-16T04:00:00-05:00`) | UTC (`2026-11-16T09:00:00+00:00`) |
| `observed_at` | when typed in | when Claude Code last answered, with microseconds |
| windows | `weekly_all`, `session`, `weekly_fable` (any subset) | `weekly_all` and `session` (either may be missing); never `weekly_fable` |
| how often | hours apart | while Claude Code is in use, a changed reading every 15 minutes at most (at once on a state change or a new week), so the newest is usually minutes old |

- Parse `pct_used` as a float. The state compares the unrounded value (80.5 is constrained);
  printed values round half to even (80.5 prints as 80, 23.5 as 24), as Python's
  `f"{x:.0f}"`, Rust's `{:.0}` and Kotlin's `BigDecimal(x).setScale(0, HALF_EVEN)` do.
- Compare timestamps as instants, never as text; a case pins that (`offsets_compare_as_instants_not_text`).
  Cases with `same_instant_as` restate another case's instants in a different offset and expect the same result.
- Judge only the newest reading. A missing `weekly_fable` is not an error, and a reader must
  not borrow one from an older manual reading.
- `note` keys in a case are comments.

## nag_damping_cases.json (#368, #349)

Inputs for a case are `base` with the case's `given` keys replacing base keys whole.
Expected output is `{verdict, reason}`; `verdicts` and `reasons` list the vocabulary.
Each case trips at most one gate, so the order an arm checks gates in does not matter.

Rules (all local times are America/New_York, hard-coded per the operator ruling;
`users.timezone` is not read):

- **Phone verified**: only `users.phone_verified = true` is eligible.
- **Vacation**: `prefs.vacation_mode` true, or `users.vacation_mode_until` after now. A past date does not block.
- **Prefs**: a NULL `users.notification_prefs` reads as `{}`, so every key takes its default.
- **Days**: `prefs.enabled_days` lists weekdays. The canonical form is the full English name
  (`monday` .. `sunday`, as the v7 migration stored it); 3-letter abbreviations (`mon` .. `sun`)
  are an alias. Match case-insensitively on the first three letters. Absent, NULL or an empty
  list means every day (the v7 migration defaulted a missing value to `[]`).
- **Types**: `prefs.message_types`, if present, must include `walk_reminder`; absent means all types.
- **Window**: the New York hour must be within `time_window_start..time_window_end`, both inclusive (defaults 13 and 17). Live prefs 14/17 mean 14:00 to 17:59.
- **Walked**: no reminder once a 2000+ step walk is recorded for today's New York date.
- **Stand-down**: Spin stands down while the `android_client` heartbeat is younger than the Spin variable `reminder_standdown_minutes` (default 240; 0 disables).
- **Damping**: no send while a counted nag is under 240 minutes old. Counted rows are any type except `phone_verification`, on channel `whatsapp` with status `sent`, `failed` or NULL, or on channel `android_native` with status `shown`. Inbound (`received`) and console (`not_sent`) rows never count.
- **Daily cap**: `prefs.max_messages_per_day` (default 3) counts `whatsapp` rows with status `sent`, `failed` or NULL, any type except `phone_verification`, whose `sent_at` falls on today's New York date. Never count by the `message_log.date` column, which Spin fills in GMT. Local phone nags (`android_native`) do not count toward the cap.
- **NULL columns fail closed**: a NULL `channel` reads as `whatsapp` (the column default), and a
  `whatsapp` row with NULL status is an outbound send. Existing writers produce such rows
  (`scheduler.py` logs `android_dark` alerts with no status; the `UndefinedColumn` fallback in
  `mcp_server.py` writes neither status nor channel). New writers should still set both.
- **Minutes**: every age is whole minutes, `floor(seconds / 60)`. In Postgres that is
  `FLOOR(EXTRACT(EPOCH FROM now() - t) / 60)::BIGINT` (a bare `CAST(... AS BIGINT)` rounds, and
  a bare division arrives in Spin as `DbValue::Decimal`); in Python, `int(seconds // 60)`. This
  applies to the stand-down heartbeat age and to pulse `minutes_since` too.
- **Future rows**: a counted row whose `sent_at` is at or after now damps (its age is negative),
  matching the SQL form `sent_at > now() - interval '240 minutes'`.

The Python send guard implements only damping and the daily cap; it consumes the
cases tagged `damping` or `daily_cap`, whose other inputs are all eligible.
