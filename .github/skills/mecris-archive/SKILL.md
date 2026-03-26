---
name: mecris-archive
description: 'Serialize session state after work is complete. Closes the plan issue, updates NEXT_SESSION.md, appends to SESSION_LOG, and commits. Handles partial completion honestly. The on-save arm. Trigger with /mecris-archive'
---

# mecris-archive

State serialization skill for the Mecris accountability system. Runs last in every session. Makes the next instance — which wakes with zero memory — whole again.

## When to Activate
- After work is complete (or as complete as it's going to get this run)
- Before stopping, always — even if nothing worked
- When the user says "archive", "wrap up", "save state", "we're done", "/mecris-archive"

## Slash Command

### `/mecris-archive`

Runs the full archive workflow:

1. Determine completion status — did the work match the plan? fully, partially, or not at all?
2. Close the plan issue with a completion comment
3. Rewrite `NEXT_SESSION.md` to reflect current reality
4. Append a dated entry to `SESSION_LOG`
5. Commit all three with a consistent message
6. Stop

**Usage**: Type `/mecris-archive` when the work is done. Always runs, even on failure.

## Step 1 — Close the Plan Issue

Find the open `[plan]` issue created this session and close it with a comment:

```
## ✅ Complete / ⚠️ Partial / ❌ Did not complete

**What happened**: {one paragraph — what was actually done, not what was planned}

**Diverged from spec**: {yes/no — if yes, explain what changed and why}

**Unfinished**: {anything from the plan that didn't get done — carried forward to NEXT_SESSION.md}

**Validation**: {did the validation criterion from the plan pass? cite evidence — test output, git log, issue number}
```

Use the honest status icon. Partial is not failure — it is accurate.

## Step 2 — Rewrite NEXT_SESSION.md

`NEXT_SESSION.md` is the state noun. It must reflect reality after this session, not before.

Structure:
```markdown
# Next Session: {one-line description of the most pressing pending item}

## Current Status ({TODAY'S DATE})
{2-5 bullet points describing what is true right now — not aspirations, facts}

## Verified This Session
{Items that were confirmed working — with [x] checkboxes}

## Pending Verification (Next Session)
{Items that need checking — specific, testable, with enough context to act without reading anything else}

## Infrastructure Notes
{Anything about the running system that is non-obvious — cron status, disabled features, schema changes}
```

Rules:
- Every pending item must be specific enough to act on cold
- If something was verified, move it to Verified — do not leave it in Pending
- If something new was discovered, add it to Pending
- Date the status block with today's date so staleness is visible

## Step 3 — Append to SESSION_LOG

Append (do not overwrite) a dated entry:

```markdown
## {DATE} — {one-line summary of what was done}

**Planned**: {what the plan issue said}
**Done**: {what actually happened}
**Skipped**: {what didn't happen and why}
**Next**: {the single most important thing for the next session}
```

## Step 4 — Commit

```
git add NEXT_SESSION.md SESSION_LOG scripts/bot-prompt.txt
git commit -m "archive({DATE}): {one-line summary}

Plan: #{issue_number}
Status: complete|partial|incomplete
Next: {most pressing pending item}"
```

## Handling Partial Completion

If the bot ran out of turns, the work failed, or scope expanded mid-run:

- **Do not pretend success** — the plan issue closes with ⚠️ or ❌
- **Carry forward explicitly** — every unfinished item goes into Pending with enough context to resume cold
- **Record why** — one sentence in the SESSION_LOG Skipped field
- **Still commit** — a partial archive is infinitely better than no archive

The integrity of the loop depends on honesty here. The next instance will trust what it reads.

## Notes

- Archive commits on behalf of the bot identity (`mecris-bot <mecris-bot@noreply>`) — git config is already set in the workflow
- Push is handled by the workflow's final step — archive does not push
- If no plan issue exists (orient → work → archive without plan), create a retrospective issue instead: title `[retro] {date} — {what was done}` and close it immediately
- SESSION_LOG lives at `session_log.md` in the repo root
