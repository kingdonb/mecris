# Requirements: Autonomous Mecris Agent (Identity-Isolated)

## Overview

Create a sandboxed autonomous agent that can operate on the Mecris repo without access to the user's personal identity, credentials, or data. The agent pushes code changes via a dedicated bot identity.

## User Stories

**As the user,** I want an autonomous agent that can make commits to the Mecris repo independently, so that automated maintenance, refactors, or feature work can happen without exposing my personal git credentials or API tokens.

**As the user,** I want the bot to have a clearly distinct git identity (name/email), so that I can always tell apart human commits from autonomous agent commits in the git log.

**As the user,** I want the agent to have the minimum permissions needed (push to Mecris only), so that a rogue or misbehaving agent cannot affect other repos or services.

## Acceptance Criteria

- [ ] A dedicated git identity (bot name + email) is configured for the agent — not the user's personal identity
- [ ] The agent uses a scoped deploy key or personal access token that grants push access to Mecris only
- [ ] Commits made by the agent are visually distinguishable in `git log` (author name, email, or commit annotation)
- [ ] The agent has no access to personal credentials (Twilio, Beeminder, Claude budget, etc.) unless explicitly granted per-task
- [ ] A documented way to invoke the agent: a script or CLI command that runs it in isolation
- [ ] The agent can open a Claude Code session (or equivalent) with the Mecris repo as workspace and produce commits

## Out of Scope

- The agent does not need to self-schedule or run as a cron job (that's a future concern)
- The agent does not need to interact with Twilio/Beeminder during autonomous runs (read-only at most)
- Multi-repo access is explicitly out of scope — Mecris only
