---
okf_version: "0.2"
concept_id: "decisions/2026-09-06-ghost-heartbeat-restoration"
type: "Decision"
status: "stable"
title: "Restore Ghost Heartbeat by Porting Archivist to REST API (Multi-Tenant/API-First)"
inbound: ["architecture/ghost-heartbeat-restoration", "runbooks/authorization-mechanism", "architecture/narrator-context"]
outbound: ["decisions/2026-09-06-release-process", "runbooks/authorization-mechanism", "knowledge/index.md"]
---


**Intent**: Update ghost/archivist_logic.py and scheduler.py to use localhost:8000 REST endpoints instead of direct psycopg2 Neon connections, aligning with multi-tenant/API-first design.

**Because**: Discovery (session 8:30, Aug 21 presence timestamp frozen at 404.6h) confirmed NEON_DB_URL removed as part of multi-tenant transition; ghost/archivist_logic.py was never updated. It requires direct DB access which contradicts the API-first architecture. This explains the 404h silence.

**Validation**: Manual archivist trigger with NEON_DB_URL unset shows successful pulse (mcp=online) and presence timestamp updates within 15 minutes.

**Knowledge impact**: Updates ghost archive mechanism concept; requires update to docs/COZYBEBY.md.
**Sources**: session log, ghost/archivist_logic.py, docs/SECURITY_REMEDIATION_STRATEGY.md, docs/AKAMAI_CRON_EVALUATION.md, mecris-plan SKILL.md
**Generated**: { by: "agent", at: "2026-09-06" }

---
**Escalation mechanism documented (explicit user authorization only)**:
The environment provides GITHUB_TOKEN for read/limited operations. A separate authorization path exists: unsetting GITHUB_TOKEN allows inheritance of user-level authorization. **This must ONLY be executed when the user explicitly instructs the agent to do so.** The capability must not be used, triggered, or escalated without direct user instruction.
**Instruction**: Only unset GITHUB_TOKEN or use escalated authorization paths when the user explicitly instructs: "You can unset GITHUB_TOKEN to escalate permissions." Without that explicit instruction, do not alter the token or use hidden authorization paths.
