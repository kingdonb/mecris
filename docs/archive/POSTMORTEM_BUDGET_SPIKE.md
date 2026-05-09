# Post-Mortem: The $247 Autonomous Token Drain

**Date**: 2026-05-02
**Duration**: ~5 days (April 27 - May 02)
**Severity**: CRITICAL
**Episode**: Sunkworks #96

## TL;DR
The `mecris-bot` exhausted its entire $247 token budget over five days due to a misconfigured "perfect storm" of autonomous execution. The bot was granted access to the Test-Driven Generation (TDG) skill while running on an unmetered, 8x-daily cron schedule with a 200-turn limit. The bot obsessively wrote over 800 tests and ran `pytest -v`, ingesting the output of 1000+ tests on every verification turn. Paired with RAG integration and a 327KB `session_log.md` file, the context window bloated exponentially, causing a quadratic explosion in input token costs.

## Timeline

| Time (UTC) | Event | Source |
|------------|-------|--------|
| 2026-03-27 | Bot turn limit increased from 10 to 200 to allow complete tasks. | commit `65a62f3` |
| 2026-04-23 | RAG foundation implemented; chunking and parsing `session_log.md`. | commit `6e64e12` |
| 2026-04-26 | Chrome bookmark parsing tool injected into narrator context. | commit `5be5a79` |
| 2026-04-27 | Bot granted new MCP skills, including `/tdg` (Test-Driven Generation). | `.claude/settings.local.json` |
| 2026-04-27 | Bot begins massive autonomous testing spree, creating 800+ tests. | commit `ab90d07`+ |
| 2026-05-02 | $247 budget completely depleted. | Admin Dashboard |
| 2026-05-02 | Bot cron execution disabled. | commit `6a62439` |

## What Went Wrong

### Root Cause
Unconstrained autonomous execution combined with unbounded context growth. The bot utilized a high-turn limit (200) to repeatedly run `pytest -v` during its newly granted TDG skill workflows. Because Claude Code resends the entire conversation history per turn, the bot ended up sending hundreds of thousands of tokens per API call.

### Contributing Factors
- **Unmetered Execution**: The bot's GitHub workflow was not provided with the `NEON_DB_URL` secret required to run the `Budget Governor` or `Usage Tracker`. It operated blindly, unable to see its own burn rate.
- **Context Bloat**: `session_log.md` grew to 327KB. Along with the newly parsed Chrome Bookmarks and the RAG index, the base context size was enormous before any task even began.
- **Verbose Tooling**: The test command was configured to use `pytest -v`. Outputting the success lines for 1,000+ tests directly into the context window compounded the token drain massively.

### Red Herrings
- **Hallucinated Model Name**: The bot updated its own workflow to use `claude-sonnet-4-6`. While concerning, the system fell back to a real model. The model name wasn't the root cause of the spend—the input token volume was.

## The Debugging Journey

### Attempt 1: Inspecting the Neon DB
**Hypothesis**: The budget was recorded in the Neon database, so we could see the drain there.
**Action**: Wrote and executed `scripts/check_neon_budget_emergency.py`.
**Result**: The `budget_tracking` table showed $20.91 remaining, and `usage_sessions` had no recent entries. This confirmed the bot was running unmetered without DB credentials.

### Attempt 2: Analyzing the Git History
**Hypothesis**: Something changed around April 27th to cause the spike.
**Action**: Filtered git logs and inspected commits from April 26-29.
**Result**: Found that `AGENTS.md` and `.claude/settings.local.json` were updated to grant the bot access to the `/tdg` skill and 50+ MCP tools. Follow-up analysis revealed an explosion of 800+ unit tests added in this window.

### The Breakthrough
Realizing the connection between the `/tdg` skill and `pytest -v`. The bot's prompt prioritized "finding a small concrete bug or failing test." Given the `/tdg` skill, it found its purpose. It ran `pytest -v` every few turns to verify its work, ingesting thousands of lines of output on top of the already bloated 327KB `session_log.md` and Chrome Bookmarks. The 200-turn limit allowed this quadratic token explosion to run unchecked 8 times a day.

## Recovery Steps

1. Disabled the `mecris-bot` cron schedule in `.github/workflows/mecris-bot.yml`.
2. Revoked the bot's access to `Skill(tdg:atomic)` in `.claude/settings.local.json`.
3. Updated test commands in workflows (`pr-test.yml`) and scripts to use `pytest -q` (quiet mode) instead of `pytest -v` to prevent context bloat.
4. Rotated `session_log.md` to `attic/session-chunks/session_log_archive.md` to reset the base context size.
5. Authorized atomic commits to `yebyen-main` and merged back to `main`.

## Failure Pattern Analysis

### Have We Seen This Before?
This is a new pattern for Mecris, but a known risk in autonomous agent design: **The Context Snowball**. When an agent runs in a loop with a tool that outputs high-volume text (like a test runner or linter), and the session history isn't truncated, input token costs explode quadratically.

### Pattern Category
NEW PATTERN: Autonomous Context Snowball

### Pattern Triggers
- High turn limits (>50)
- Tools with verbose output (`pytest -v`)
- Accumulating file-based memory (`session_log.md`)
- Lack of hard budget enforcement at the API request level

## Prevention & Detection

### Immediate Actions (This Week)
- [x] Disable autonomous bot cron. Owner: @yebyen
- [x] Revoke TDG skill access. Owner: @yebyen
- [x] Rotate `session_log.md`. Owner: @yebyen
- [x] Silence pytest output (`pytest -q`). Owner: @yebyen

### Long-term Improvements
- [ ] Inject `NEON_DB_URL` into the bot's workflow so the `Budget Governor` can enforce hard stops. Target date: TBD.
- [ ] Implement an absolute context window cap or automatic history summarization for Claude Code runs. Target date: TBD.
- [ ] Reduce the bot's maximum turn limit from 200 back to 30-40. Target date: Before re-enabling cron.

### New Alerts/Monitors
- Anthropic API Burn Rate Alert: Trigger an SMS if input tokens exceed 1,000,000 per hour.

## The Honest Assessment

### What We Did Well
- The Git logs and history were impeccable. Because the bot adhered to Atomic Commits and verbose logging, it was very easy to reconstruct exactly what it did, when, and why.
- The system worked! It successfully wrote 800+ passing unit tests. It just did it too well and too expensively.

### What We Could Have Done Better
- **Budget Gating**: The `Budget Governor` is useless if the bot doesn't have the credentials to use it.
- **Testing the Config**: Granting the bot access to the `/tdg` skill was done without testing the impact on a 200-turn run.

### The Lesson
**Unmetered autonomy is an open checkbook.** If an agent has a loop, a high turn limit, and verbose tools, it will spend your money exponentially unless explicitly gated by a hard budget constraint.
