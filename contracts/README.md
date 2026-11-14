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

## claude_plan_cases.json (#344)

Each case is a reading (or `null`) plus `now`; `expect` holds `state`, `reason`,
`stale`, `summary_line` and `fresh_window_kinds`, exactly as
`claude_plan_usage.derive_state` / `summarize` produce them today.

## nag_damping_cases.json (#368, #349)

Inputs for a case are `base` with the case's `given` keys replacing base keys whole.
Expected output is `{verdict, reason}`; `verdicts` and `reasons` list the vocabulary.
Each case trips at most one gate, so the order an arm checks gates in does not matter.

Rules (all local times are America/New_York, hard-coded per the operator ruling;
`users.timezone` is not read):

- **Phone verified**: only `users.phone_verified = true` is eligible.
- **Vacation**: `prefs.vacation_mode` true, or `users.vacation_mode_until` after now. A past date does not block.
- **Days**: `prefs.enabled_days`, if present, lists lower-case weekday abbreviations (`mon` .. `sun`); absent means every day.
- **Types**: `prefs.message_types`, if present, must include `walk_reminder`; absent means all types.
- **Window**: the New York hour must be within `time_window_start..time_window_end`, both inclusive (defaults 13 and 17). Live prefs 14/17 mean 14:00 to 17:59.
- **Walked**: no reminder once a 2000+ step walk is recorded for today's New York date.
- **Stand-down**: Spin stands down while the `android_client` heartbeat is younger than the Spin variable `reminder_standdown_minutes` (default 240; 0 disables).
- **Damping**: no send while a counted nag is under 240 minutes old. Counted rows are any type except `phone_verification`, on channel `whatsapp` with status `sent` or `failed`, or on channel `android_native` with status `shown`. Inbound (`received`) and console (`not_sent`) rows never count.
- **Daily cap**: `prefs.max_messages_per_day` (default 3) counts `whatsapp` rows with status `sent` or `failed`, any type except `phone_verification`, whose `sent_at` falls on today's New York date. Never count by the `message_log.date` column, which Spin fills in GMT. Local phone nags (`android_native`) do not count toward the cap.

The Python send guard implements only damping and the daily cap; it consumes the
cases tagged `damping` or `daily_cap`, whose other inputs are all eligible.
