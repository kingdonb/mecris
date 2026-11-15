---
title: "Claude plan usage"
description: "How Mecris learns how much of the Claude subscription plan is used, without usage credits and without typing it in"
---

# Claude plan usage

Mecris tracks how much of the Claude **subscription plan** is used: the five-hour
session window and the weekly window. It does not track dollars and it never
touches usage credits. Tracking issue: kingdonb/mecris#344.

## Where the numbers come from

Anthropic has no public API for plan usage. Claude Code does pass the numbers to a
[status line command](https://code.claude.com/docs/en/statusline), as JSON on stdin:

```json
"rate_limits": {
  "five_hour": { "used_percentage": 23.5, "resets_at": 1738425600 },
  "seven_day": { "used_percentage": 41.2, "resets_at": 1738857600 }
}
```

`scripts/claude_statusline.py` is that command. Nothing is scraped and no cookie
or token is read.

## Setup

Add this to `~/.claude/settings.json`, with the path to your checkout:

```json
"statusLine": {
  "type": "command",
  "command": "/usr/bin/python3 /path/to/mecris/scripts/claude_statusline.py"
}
```

The script needs only the Python standard library (3.9 or later). The status bar
then shows `5h 16% · wk 24%`, and each Claude Code response updates the snapshot.

## The snapshot file

`~/.claude/usage.json` (set `CLAUDE_USAGE_SNAPSHOT` to move it). Any local
dashboard can read it:

```json
{
  "schema": 1,
  "source": "claude_code_cli",
  "observed_at": "2026-11-14T23:50:00+00:00",
  "checked_at": "2026-11-14T23:52:10+00:00",
  "windows": [
    { "kind": "weekly_all", "pct_used": 23.5, "resets_at": "2026-11-16T09:00:00+00:00" },
    { "kind": "session", "pct_used": 16.4, "resets_at": "2026-11-15T00:50:00+00:00" }
  ]
}
```

- `session` is the five-hour window and `weekly_all` is the weekly one. A window
  that Claude Code does not report is absent.
- `observed_at` is when these numbers last arrived with a response from
  Anthropic. `checked_at` is when the script last ran. The status line also
  re-runs on timers and mode changes, which is not new information, so only
  `observed_at` says how old the numbers are.
- A window whose `resets_at` has passed is out of date. Treat it as unknown, not
  as zero.
- The file also holds a `sessions` map, used to tell a new response from a re-run.

## What Mecris does with it

- `get_claude_plan_status` and `get_narrator_context` use the snapshot when it is
  newer than the latest stored reading. Only the local user gets it.
- Every five minutes the MCP server stores the snapshot in Neon as a
  `claude_code_cli` reading, if a window has moved by a point or more since the
  last stored reading. It stores at most one reading per 15 minutes, except that
  a change of state (for example available to constrained) or a new week is
  stored at once. Stored readings feed the Beeminder graph the same way manual
  ones do.
- Only the scheduler leader stores. Every process that starts the scheduler
  (`mcp_server.py`, `mcp_stdio_server.py` and `simple_main.py`) runs the
  five-minute check, and Claude Desktop alone starts several, but a standby
  process skips it: while another process leads, this one never stores.
  Leadership is checked on each run, so after a handover the new leader takes
  over at its next check.
- A process that finds the leader slot free (a clean shutdown frees it) is
  usually leader by its first check and stores at once. If the slot is still
  held by a process that died without freeing it, the slot is taken over once
  that heartbeat is 90 seconds old (elections run every 30 seconds), and the
  first store comes at the next five-minute check.
- The leader stores the snapshot in its own `HOME`. A leader on a machine with
  no `~/.claude/usage.json` stores nothing, even if another machine has one.
- The check logs each change of outcome to the server log as
  `Claude snapshot ingest: ...` (for example `not the scheduler leader`,
  `no status line snapshot`, `stored a reading`, `nothing new`), so a process
  that never stores can be told apart from one with nothing new to store.
- A reading is not stored twice. The insert skips a reading whose user, source
  and `observed_at` are already stored, in the same statement, and nothing is
  pushed to Beeminder when it skips. There is no unique index on those columns,
  so two inserts at the same instant (say, two leaders during a handover) could
  still both land. The check narrows that race; only a unique index would close
  it, and adding one needs any existing duplicates removed first.

## Rounding

Every display rounds a percentage to a whole number with round half to even:
22.5 shows as 22 and 23.5 as 24. The status line (`f"{x:.0f}"`) and
`get_claude_plan_status` (`'{:.0f}'`) use this rule. The Spin display (Rust
`{:.0}`, on `feat/v0.3-spin-status`) and the Android display (Kotlin
`HALF_EVEN`, on `feat/v0.3-android`) use it too, but neither branch is merged
yet; once they are, every display shows the same number. The stored and
snapshot values keep their decimals.

## Limits

- The snapshot only updates while Claude Code is making requests. Usage from
  claude.ai or the desktop app appears at the next Claude Code response.
- Claude Code does not report the per-model weekly window (`weekly_fable`).
  Record that one with `record_claude_plan_usage` if it matters.
- `rate_limits` is absent until a session's first response.
