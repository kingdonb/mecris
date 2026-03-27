---
name: mecris-pr-test
description: 'Dispatch the pr-test workflow for a PR number from kingdonb/mecris. Polls for completion and summarizes results. Wraps the full test pipeline (pytest + Android) as an invocable skill. Use when an issue is tagged needs-test or pr-review. Trigger with /mecris-pr-test <PR_NUMBER>'
---

# mecris-pr-test

Pipeline skill for the Mecris accountability system. Dispatches the pr-test GitHub Actions workflow against an upstream PR, polls until complete, and reports results. The test pipeline itself runs pytest against local postgres and Android unit tests via Gradle — no Neon credentials needed.

## When to Activate
- Orient found an issue tagged `needs-test` or `pr-review` referencing a PR number
- User says "test PR 141", "run pr-test for #142", "/mecris-pr-test 143"
- After a plan issue specifies triggering pr-test as the action

## Slash Command

### `/mecris-pr-test <PR_NUMBER>`

Runs the full pipeline workflow:

1. Dispatch `pr-test.yml` on `yebyen/mecris` with the given PR number
2. Poll the workflow run until status is `completed` (check every 30s, timeout 15min)
3. Report the conclusion — success or failure — with a link to the run
4. If successful, close any `needs-test` issue that triggered this
5. If failed, note the failure in the plan issue for archive to record

**Usage**: `/mecris-pr-test 141` — dispatches and polls, returns when done.

## Step 1 — Dispatch

```bash
curl -X POST \
  -H "Authorization: Bearer $GITHUB_CLASSIC_PAT" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  -d '{"ref":"main","inputs":{"pr_number":"<N>","upstream_repo":"kingdonb/mecris"}}' \
  https://api.github.com/repos/yebyen/mecris/actions/workflows/pr-test.yml/dispatches
```

Requires `GITHUB_CLASSIC_PAT` (repo scope). In bot context this is already in the environment. In human context source `~/.mecris-bot.env`.

## Step 2 — Poll

After dispatching, wait 10 seconds then fetch the most recent run of `pr-test`:

```bash
curl -s \
  -H "Authorization: Bearer $GITHUB_CLASSIC_PAT" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/yebyen/mecris/actions/runs?per_page=5" \
  | python3 -c "
import sys,json
runs = json.load(sys.stdin)['workflow_runs']
pr_runs = [r for r in runs if r['name'] == 'pr-test']
if pr_runs:
    r = pr_runs[0]
    print(r['id'], r['status'], r['conclusion'])
"
```

Poll every 30 seconds until `status == completed`. Timeout after 15 minutes — if it hasn't finished, record as inconclusive and archive anyway.

## Step 3 — Report

On completion:

| Conclusion | Action |
|---|---|
| `success` | Report ✅, close any `needs-test` issue, note in plan issue |
| `failure` | Report ❌, link to run logs, note specific failing step if known |
| `timeout` | Report ⏱️ inconclusive, leave needs-test issue open |

The pr-test workflow itself posts a detailed comment on the upstream PR. This skill just reports the top-level conclusion to the current session.

## What the Pipeline Actually Tests

- **Python tests**: `pytest tests/` against a local postgres:16 service container — no Neon credentials needed
- **Android unit tests**: `./gradlew testDebugUnitTest` in `mecris-go-project/` with JDK 17 — no emulator needed
- **Merge**: fetches the upstream PR branch and merges into `yebyen/mecris:main` before testing

Results are posted as a comment on the upstream PR by `yebyen` (the bot's identity).

## Notes

- `GITHUB_CLASSIC_PAT` is required — fine-grained PATs cannot trigger `workflow_dispatch`
- The workflow run takes 3-8 minutes typically — polling is necessary, not optional
- If the workflow name shows as the file path (`.github/workflows/pr-test.yml`) instead of `pr-test`, there is a YAML parse error in the workflow file — do not poll, investigate instead
- One PR at a time — do not dispatch multiple runs concurrently
- The upstream repo defaults to `kingdonb/mecris` — pass `upstream_repo` input to override
