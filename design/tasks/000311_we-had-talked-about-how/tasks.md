# Implementation Tasks

## Status: Existing Implementation (Already Complete)

The isolated autonomous agent is already implemented and operational. This task documents the existing system and addresses one remaining issue.

### ✅ Phase 1: Identity Isolation (Complete)

- [x] Create separate GitHub identity (`yebyen`) for bot operations
- [x] Fork `kingdonb/mecris` to `yebyen/mecris` 
- [x] Configure bot to work exclusively on the fork
- [x] Set up PR-based workflow for changes to reach upstream

### ✅ Phase 2: Credential Setup (Complete)

- [x] Create fine-grained PAT scoped to `yebyen/mecris` only (`MECRIS_BOT_PAT`)
- [x] Create classic PAT for cross-repo PR operations (`MECRIS_BOT_CLASSIC_PAT`)
- [x] Configure Helix API token (`MECRIS_BOT_ANTHROPIC_KEY`)
- [x] Store all secrets in `yebyen/mecris` repository settings only

### ✅ Phase 3: Workflow Configuration (Complete)

- [x] Create `mecris-bot.yml` workflow with scheduled runs (8x/day)
- [x] Configure git identity as `mecris-bot` / `mecris-bot@noreply`
- [x] Implement skill-based agent loop (`/mecris-orient`, `/mecris-plan`, `/mecris-archive`)
- [x] Configure push to `yebyen/mecris:main` after each run

### ✅ Phase 4: Human Review Gate (Complete)

- [x] Bot opens PRs from `yebyen/mecris` to `kingdonb/mecris`
- [x] Human (Kingdon) reviews PRs using Gemini agent (per `GEMINI.md`)
- [x] Verified: Open PR #153 awaiting review

## Fix Required: Prevent Upstream Workflow Failures

- [ ] Add `if: github.repository == 'yebyen/mecris'` condition to `mecris-bot.yml`
  - **Issue**: Workflow runs 8x/day on `kingdonb/mecris` but fails due to missing secrets
  - **Impact**: Clutters Actions history with 8 failures per day
  - **Fix**: Skip job entirely when running on upstream repo

## Verification Completed

- [x] Confirmed bot commits appear as `mecris-bot`, not personal identity
- [x] Confirmed fine-grained PAT cannot access other repos
- [x] Confirmed 5+ days of successful autonomous operation (see `session_log.md`)
- [x] Confirmed PR workflow functioning (PR #153 open, previous PRs merged)