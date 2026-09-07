---

okf_version: "0.2"
concept_id: "authorization/mechanism"
type: "Runbook"
status: "stable"
title: "Authorization Mechanism: GITHUB_TOKEN Escalation (Explicit Only)"
inbound: ["knowledge/index", "2026/09/06/ghost/heartbeat/restoration", "2026/09/06/release/process", "runbooks/multi-model-collaboration"]
outbound: ["knowledge/index", "2026/09/06/ghost/heartbeat/restoration", "2026/09/06/release/process", "runbooks/multi-model-collaboration"]

  relationships:
    - target: "2026/09/06/ghost/heartbeat/restoration"
      description: "executed for fix PR #297 merge and release"
    - target: "2026/09/06/release/process"
      description: "used for release sequence authorization"
---



**Intent**: Document the authorization escalation mechanism for GitHub operations in Mecris, with strict authorization guard.

**Mechanism**: The environment provides `GITHUB_TOKEN` for standard operations. A separate authorization path exists: unsetting `GITHUB_TOKEN` allows inheritance of user-level authorization (e.g., `gh auth token` keyring access). This mechanism must ONLY be executed when the user explicitly instructs: "You can unset GITHUB_TOKEN to escalate permissions." Without that explicit instruction, the agent must NOT alter the token or use hidden authorization paths.

**Usage in session (2026-09-06)**: Executed for PR #297 merge (`kingdonb/mecris`) and release tag `v0.0.3` after explicit user authorization.

**Guard**: Only execute when user explicitly states authorization phrase. Always document execution in OKF with provenance.
**Sources**: AGENTS.md, session logs (2026-09-06), `.github/workflows/mecris-bot.yml`
**Generated**: { by: "agent", at: "2026-09-06" }

## Related Concepts
- [Restore Ghost Heartbeat by Porting Archivist to REST API (Multi-Tenant/API-First)](../decisions/2026-09-06-ghost-heartbeat-restoration.md): Executed for fix PR #297 merge and release.
- [Mecris Release Process: PR Before Tag (Correct Sequence)](../decisions/2026-09-06-release-process.md): Used for release sequence authorization.
