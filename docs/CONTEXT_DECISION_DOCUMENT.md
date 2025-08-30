# Context‑Decision‑Document (CDD) Pattern

## Overview
The **Context‑Decision‑Document (CDD) pattern** structures interactions that require:
1. **Reference to external context** – e.g., repository layout, configuration, or any outside information.
2. **Inference/decision** – a binary (yes/no) or multi‑option judgment derived from that context.
3. **Document generation** – a persistent artifact that records the reasoning, the decision outcome, and actionable next steps.

This pattern enforces traceability and clear communication, which is essential for security‑sensitive changes and for maintaining institutional knowledge.

## Why use the CDD pattern?
- **Auditability:** Every decision is backed by documented evidence.
- **Collaboration:** Team members can quickly understand why a choice was made and what to do next.
- **Consistency:** Repeating the same structured approach reduces ad‑hoc reasoning.
- **Safety:** Especially for defensive security tasks, having a written rationale helps reviewers spot missed considerations.

## How to apply it
1. **Gather Context** – Identify and cite the external source (e.g., a file, a command output, a policy).
2. **Make a Decision** – Evaluate the context and choose an action. Clearly state the possible outcomes (e.g., *yes* to implement, *no* to reject).
3. **Create the Document** – Record:
   - The original context (with links or excerpts).
   - The decision and its justification.
   - Impact statements or instructions for subsequent work.
4. **Store the Document** – Place it in a shared location (e.g., `docs/` folder) with a descriptive name.

## Example in this repository
- **Context:** The repository contains a deep `src` hierarchy with many `.py` and `.pyc` files.
- **Decision:** Show the tree up to depth 3, hide Python source files, and prune empty directories.
- **Document:** `docs/Tree_Usage_Guideline.md` (already created) records the command, rationale, and next steps.

The CDD pattern was used to produce that guideline, demonstrating the workflow.

## Next Steps for the Team
- Adopt the CDD naming convention for future decisions.
- Store all CDD files under `docs/` for easy discovery.
- Review existing decisions and retroactively capture them using this pattern.

---
*Generated with Claude Code.*