---

okf_version: "0.2"
concept_id: "ghost/heartbeat/restoration"
type: "Architecture"
status: "stable"
title: "Ghost Heartbeat Restoration via REST API (Multi-Tenant/API-First)"
inbound: ["knowledge/index", "architecture/narrator-context", "runbooks/agent-bootstrap", "runbooks/multi-model-collaboration"]
outbound: ["knowledge/index", "2026/09/06/ghost/heartbeat/restoration", "2026/09/06/release/process", "authorization/mechanism", "runbooks/multi-model-collaboration"]

  relationships:
    - target: "2026/09/06/ghost/heartbeat/restoration"
      description: "documents mechanism change"
    - target: "2026/09/06/release/process"
      description: "included in v0.0.3 release"
---



**Intent**: Restore the ghost archivist's heartbeat functionality through the REST API (`localhost:8000/heartbeat`) instead of direct Neon database access (`NEON_DB_URL`), aligning with the multi-tenant/API-first design.

**Because**: The multi-tenant transition (`docs/SECURITY_REMEDIATION_STRATEGY.md`) removed direct DB dependency (`NEON_DB_URL`) but `ghost/archivist_logic.py` was never updated. This caused a 404-hour silence (`last_ghost_activity` frozen at Aug 21) because the writer (`archivists_round_robin`) had no DB destination. The fix uses the REST endpoint (server retains DB access; client uses API only).

**Mechanism**: `perform_archival_sync()` calls `/heartbeat` (POST, `role=active_ghost`, `user_id`) instead of `store.upsert()`. `mcp_server.py` endpoint writes `ACTIVE_GHOST` to the Neon `presence` table.

**Validation**: Manual trigger with `NEON_DB_URL` unset shows `mcp=online` response; server responds to `/heartbeat` (401 = endpoint loaded); tests updated (`tests/test_ghost_archivist.py`).

**Sources**: session logs (2026-09-06), `ghost/archivist_logic.py`, `mcp_server.py`, `docs/SECURITY_REMEDIATION_STRATEGY.md`, `docs/COZYBEBY.md`
**Generated**: { by: "agent", at: "2026-09-06" }
