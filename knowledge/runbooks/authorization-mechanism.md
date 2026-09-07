---
okf_version: "0.2"
concept_id: "runbooks/authorization-mechanism"
type: "Runbook"
status: "stable"
title: "Authorization Mechanism: GITHUB_TOKEN Escalation (Explicit Only)"
inbound: ["decisions/2026-09-06-ghost-heartbeat-restoration", "decisions/2026-09-06-release-process"]
outbound: ["decisions/2026-09-06-ghost-heartbeat-restoration", "decisions/2026-09-06-release-process"]
---


**Intent**: Document the authorization escalation mechanism for GitHub operations in Mecris, with strict authorization guard.

**Mechanism**: The environment provides `GITHUB_TOKEN` for standard operations. A separate authorization path exists: unsetting `GITHUB_TOKEN` allows inheritance of user-level authorization (e.g., `gh auth token` keyring access). This mechanism must ONLY be executed when the user explicitly instructs: "You can unset GITHUB_TOKEN to escalate permissions." Without that explicit instruction, the agent must NOT alter the token or use hidden authorization paths.

**Usage in session (2026-09-06)**: Executed for PR #297 merge (`kingdonb/mecris`) and release tag `v0.0.3` after explicit user authorization.

**Guard**: Only execute when user explicitly states authorization phrase. Always document execution in OKF with provenance.
**Sources**: AGENTS.md, session logs (2026-09-06), `.github/workflows/mecris-bot.yml`
**Generated**: { by: "agent", at: "2026-09-06" }
