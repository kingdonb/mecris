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

## Limits

- The snapshot only updates while Claude Code is making requests. Usage from
  claude.ai or the desktop app appears at the next Claude Code response.
- Claude Code does not report the per-model weekly window (`weekly_fable`).
  Record that one with `record_claude_plan_usage` if it matters.
- `rate_limits` is absent until a session's first response.
