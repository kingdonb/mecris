---
name: chore-cli-inventory
description: 'Weekend chore 5-minute survey, inventory, and terminal dashboard verification for the Mecris CLI (PocketID login, Rich terminal pulse, presence lock, and nag heuristics). Trigger with /chore-cli-inventory'
allowed-tools: ['run_command', 'view_file', 'grep_search', 'list_dir', 'call_mcp_tool']
---

# Weekend Chore: Mecris CLI Inventory & Dashboard Survey

Part of the **Weekend Chores** accountability workflow. This skill runs a 5-minute inventory, command suite verification, and live terminal dashboard check using the Mecris Command Line Interface (`cli/main.py`).

## The Weekend Chores Cadence

- **Frequency**: 5-minute chores must be performed **both days** of the weekend (Saturday and Sunday) to count as completed.
- **Lookback & Flair**: During Sunday's second weekend chore pass, a lookback verifies weekly continuous completion.
- **Rule of Engagement**: Run diagnostics, verify CLI outputs, and record observations into skill documents without mutating core logic.

---

## Mecris CLI Architecture Matrix

```
                      +-----------------------------+
                      |   PocketID OIDC (Home LAN)  |
                      |  https://metnoom.urmanac.com |
                      +--------------+--------------+
                                     |
                          mecris login (PKCE)
                                     v
+-----------------------------------------------------------------+
|                        Mecris Python CLI                        |
|                                                                 |
|   +-------------------+  +-------------------+  +------------+  |
|   |   mecris pulse    |  |  mecris presence  |  | mecris nag |  |
|   |  (Rich Terminal   |  |   (Ghost Session  |  | (Heuristic |  |
|   |   Ecosystem View) |  |   /tmp Lockfile)  |  |  Evaluation|  |
|   +---------+---------+  +---------+---------+  +-----+------+  |
|             |                      |                  |         |
+-------------|----------------------|------------------|---------+
              v                      v                  v
+-------------------------------+  +--------------------------+
| Neon Serverless Postgres DB   |  | FastMCP Server Bridge    |
| (Goals, Runway, Heartbeats)   |  | (Notification / Twilio)  |
+-------------------------------+  +--------------------------+
```

---

## Command Inventory: Mecris CLI (`cli/`)

| Sub-Command | Script Handler | Purpose |
|---|---|---|
| `login` | `cli/main.py:run_login` | PKCE OIDC login via PocketID (`metnoom.urmanac.com`), caches JWT in `~/.mecris/credentials.json`. |
| `pulse` | `cli/pulse.py:run_pulse` | High-density terminal dashboard showing goal runways (`SAFE`/`CRITICAL`), budget, walk status, and heartbeats. |
| `presence` | `cli/main.py:run_presence` | Manages human presence lock (`/tmp/mecris_presence.lock`) to gate or yield autonomous Ghost turns. Actions: `check`, `take`, `release`. |
| `nag` | `cli/main.py:run_nag` | Evaluates nagging tiers (`eval`) or dispatches notifications (`trigger`, `--force`). |
| `internal` | `cli/main.py:run_internal` | Maintenance hooks for data integrity and manual sync passes. |

---

## 5-Minute Chore Checklist (`/chore-cli-inventory`)

### 1. Terminal Pulse Dashboard Check
```bash
.venv/bin/python -m cli.main pulse
```
- **Expected**: Renders Rich tables for Goal Runways, Budget, Walk Status, Heartbeats, and Urgent alerts.

### 2. Presence Lock Inspection
```bash
.venv/bin/python -m cli.main presence check
```
- **Expected**: Reports whether a human lock is active at `/tmp/mecris_presence.lock`.

### 3. Nag Heuristic Evaluation
```bash
.venv/bin/python -m cli.main nag eval
```
- **Expected**: Outputs JSON heuristic evaluation (`should_send`, `tier`, `reason`).

### 4. Credentials & Token Health
```bash
cat ~/.mecris/credentials.json | jq '{user_id, familiar_id, expires_in}'
```
