---
name: mecris-orient
description: 'Produce a structured situation report for mecris-bot or a human session. Reads NEXT_SESSION.md, recent commits on yebyen/mecris and kingdonb/mecris, and open GitHub issues. Use at the start of every session before deciding what to do. Trigger with /mecris-orient'
---

# mecris-orient

Orientation skill for the Mecris accountability system. Produces a structured situation report before any action is taken. Works for both autonomous bot runs and human sessions.

## When to Activate
- At the start of every mecris-bot run, before choosing an action
- When a human session begins and wants to know the current state
- When the user says "orient", "what's the situation", "where were we", "/mecris-orient"

## Slash Command

### `/mecris-orient`

Runs the full orientation workflow autonomously:

1. Read `NEXT_SESSION.md` — pending verifications, last known state
2. Read recent git log on current repo (`git log --oneline -10`)
3. Fetch open issues from kingdonb/mecris filtered by labels: `needs-test`, `pr-review`, `bug`
4. Fetch open issues from yebyen/mecris (the bot's own issues and health reports)
5. Check if yebyen/mecris is behind kingdonb/mecris main (upstream sync status)
6. Produce the situation report (see format below)

**Usage**: Type `/mecris-orient` and the full report will be generated before any other action.

## Situation Report Format

```
## 🧭 Mecris Orientation — {DATE}

### Pending from last session
{Items from NEXT_SESSION.md that are unverified or incomplete}

### Recent commits (this repo)
{Last 5 commits, one line each}

### Upstream sync status
{Ahead/behind kingdonb/mecris main by N commits — or: up to date}

### Open issues needing action
{List of issues tagged needs-test, pr-review, or bug — with numbers and titles}

### Recommended action
{Single highest-priority item based on the above, with rationale}
```

## Priority Logic for Recommended Action

1. If any issue is tagged `needs-test` or `pr-review` referencing a PR number → trigger pr-test
2. If yebyen/mecris is behind kingdonb/mecris → sync from upstream
3. If any issue is tagged `bug` with no linked PR → that is the work
4. If NEXT_SESSION.md has unverified pending items → investigate and report
5. If nothing else → open a health report issue summarizing repo state

## Notes

- This skill reads only — it does not commit, push, or post anything
- The recommended action is a suggestion; the caller decides whether to act
- In bot context, the recommended action feeds directly into `/mecris-plan`
- In human context, the report is presented for review before proceeding
