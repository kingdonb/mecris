---

okf_version: "0.2"
concept_id: "2026/09/06/release/process"
type: "Decision"
status: "stable"
title: "Mecris Release Process: PR Before Tag (Correct Sequence)"
inbound: ["knowledge/index", "decisions/2026-09-06-ghost-heartbeat-restoration", "runbooks/authorization-mechanism"]
outbound: ["knowledge/index", "decisions/2026-09-06-ghost-heartbeat-restoration", "runbooks/authorization-mechanism"]

  relationships:
    - target: "architecture/ghost-heartbeat-restoration"
      description: "documents verified release sequence for v0.0.3"
    - target: "runbooks/authorization-mechanism"
      description: "references authorization mechanism documentation"
---



**Intent**: Document the verified release sequence and authorization guard for Mecris releases.

**Because**: During v0.0.3 release preparation, the tag `v0.0.3` was created prematurely (before PR #297/298 merged). The correct sequence is: fix PR → CI passes → merge PR → pull `main` → tag `v` on `main` → push tag. The authorization mechanism (`unset GITHUB_TOKEN`) must only be used when explicitly instructed by the user.

**Validation**: PR #297 (fix) merged on `kingdonb/mecris`; PR #298 (release) exists on correct repo (`kingdonb/mecris`, not `yebyen/mecris`); tag `v0.0.3` recreated after merge.

**Knowledge impact**: Updates release process documentation. References `docs/RELEASE_PROCESS.md`.
**Sources**: docs/RELEASE_PROCESS.md, session logs (2026-09-06), git tags (`v0.0.3`), PR #297/#298 on `kingdonb/mecris`
**Generated**: { by: "agent", at: "2026-09-06" }

## Related Concepts
- [Restore Ghost Heartbeat by Porting Archivist to REST API (Multi-Tenant/API-First)](../decisions/2026-09-06-ghost-heartbeat-restoration.md): Documents verified release sequence for v0.0.3.
- [Authorization Mechanism: GITHUB_TOKEN Escalation (Explicit Only)](../runbooks/authorization-mechanism.md): References authorization mechanism documentation.
