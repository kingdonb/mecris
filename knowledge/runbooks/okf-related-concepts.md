---
okf_version: "0.2"
concept_id: "runbooks/okf-related-concepts"
type: "Runbook"
status: "stable"
title: "Preventing and Fixing Orphan Documentation in OKF Bundles"
inbound: ["knowledge/index", "runbooks/multi-model-collaboration", "runbooks/okf-maintenance"]
outbound: ["runbooks/multi-model-collaboration", "runbooks/okf-maintenance", "knowledge/index"]
---

**Intent**: Document the verified mechanism for preventing and resolving orphan warnings (`orphan (no concept links in or out)`) identified by `okf-validate` strict mode.

**Because**: During the v0.0.3 OKF fix cycle (`2026-09-06`), `runbooks/multi-model-collaboration.md` showed `1 orphan` (`runbooks/multi-model-collaboration`) despite having `inbound`/`outbound` arrays in its frontmatter. The `okf-validate` tool requires both exact `concept_id` cross-references in `inbound`/`outbound` arrays *and* body-level concept links (e.g., `## Related Concepts`) so the graph is bidirectional and discoverable.

**Mechanism**:
1. Every new concept must declare `concept_id`, `inbound`, and `outbound` arrays using exact `concept_id` values (not file paths like `architecture/narrator-context.md`).
2. File-based link names in `inbound`/`outbound` arrays are recognized by `okf-validate` only when the target file contains a matching `concept_id` field.
3. Every concept must also contain body-level links (`## Related Concepts`, `## Relationships`) referencing the concepts it connects to, using file paths or `concept_id` references.
4. When `okf-validate --strict --drift` reports an orphan, the fix is: (a) add `concept_id` fields to referenced files if missing, (b) replace file-based link names with exact `concept_id` values in `inbound`/`outbound`, (c) add body-level `## Related Concepts` links from the referencing files to the orphaned file.

**Validation**: `tests/test_okf_release_docs.py::test_release_docs_pass_validation` passes (`0` orphan warnings). `okf validate knowledge --strict --drift` shows `Conformant` with `0` orphan(s).

**Knowledge impact**: Updates `runbooks/multi-model-collaboration`, `runbooks/okf-maintenance`, `decisions/2026-09-06-release-process`, `decisions/2026-09-06-ghost-heartbeat-restoration`, `runbooks/authorization-mechanism`, `architecture/ghost-heartbeat-restoration`.
**Sources**: `knowledge/runbooks/multi-model-collaboration.md` (§OKF Reference Fix), `.agents/skills/okf-memory/relationships.md`, `/tmp/final_agentworld_fix.md`, `tests/test_okf_release_docs.py`, `tests/test_okf_orphan_fix.py`
**Generated**: { by: agent, at: 2026-09-06 }

## Related Concepts
- [Multi-Model Collaboration for Complex Problem Resolution](multi-model-collaboration.md): The validated collaboration pattern that identified the orphan mechanism.
- [OKF Knowledge Base Maintenance](okf-maintenance.md): Periodic tasks including validation and stale checks.
