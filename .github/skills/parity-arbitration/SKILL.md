---
name: parity-arbitration
description: 'Standard protocol for identifying, documenting, and resolving behavioral discrepancies and semantic divergences across multiple arms (Android, Web, CLI, Spin WASM, Python MCP) of the Mecris ecosystem. Trigger with /parity-arbitration'
allowed-tools: ['run_command', 'view_file', 'grep_search', 'list_dir', 'call_mcp_tool', 'write_to_file', 'replace_file_content']
---

# Parity Arbitration: Cross-Arm Discrepancy Protocol

This skill outlines the standard operational protocol when two or more redundant arms in the Mecris suite (Android Compose, React Web, Python CLI, Spin WASM Edge, FastMCP) diverge in business logic, state computation, scoring heuristics, or user experience presentation.

---

## 🚨 Parity Divergence vs. Missing Feature

- **Missing Feature**: An arm does not yet support a capability (e.g. CLI lacks interactive radio lever spots). Handled as standard backlog.
- **Parity Divergence (Active Discrepancy)**: Two arms actively display contradictory interpretations of the same underlying user reality (e.g. Web displaying **STABLE (Green Orb)** while Android displays **CRITICAL (Red Orb)** for identical 2/3 goal completion). This breaks the trust boundary and confuses the human operator.

---

## The 5-Step Parity Protocol

### Step 1: Open Parity Issue & Define Ground Truth
- Open a GitHub issue labeled `bug`, `parity`, `architectural-drift`.
- **Divergence Matrix**: Explicitly table the disagreeing behaviors:
  ```markdown
  | Arm | Code Location | Observed Behavior | Underlying Formula |
  |---|---|---|---|
  | **Web** | `web/src/Dashboard.tsx` | Green Orb (`STABLE`) | `satisfied_count / total_count >= 0.5` |
  | **Android** | `app/.../MainActivity.kt` | Red Orb (`CRITICAL`) | `hasWalked || steps >= 2000` |
  ```
- **Authoritative Ground Truth**: Define which interpretation represents the canonical Mecris business logic (e.g. holistic Majesty Cake multi-goal momentum vs legacy single-sensor rule).

### Step 2: Formulate Red-Green Test Specification & CI Red Verification (TDG)
- Identify or create the unit test in the diverging client/service repository.
- Write an explicit unit test capturing the holistic contract:
  - *Example (Android)*: In `MomentumVisualizerTest.kt`, assert that 2/3 goals satisfied produces `isStable = true` (Green Orb) even if `walkData.totalSteps < 2000`.
- Verify the test fails locally or push the test-first commit to verify that CI reports a **RED** failure pipeline. Document the red CI run link/log in the issue or PR description.

### Step 3: Implement Harmonized Implementation
- Refactor the diverging arm to share the canonical formula or consume the unified backend contract from Neon/WASM.
- Remove hardcoded client-side deviations unless explicitly governed by a local sensor exception.

### Step 4: Validate Green across All Arms in CI
- Execute the unit suite on the modified arm locally.
- Leverage the **GitHub Actions CI pipeline** (`ci.yml`) to verify that all cross-platform suites turn **GREEN**:
  - `make test-python` & `make test-rust`
  - `npm run test` (Web Vitest)
  - `./gradlew testDebugUnitTest` (Android JVM unit tests)
- Record the **GREEN** CI run link in the pull request to prove cross-arm harmony.

### Step 5: Document in Release Notes & Archive
- Reference the Parity Issue in the PR title and description:
  - `"fix(parity): align Android momentum orb calculation with Web holistic 3/3 score (fixes #NNN)"`
- Add a dedicated **Parity Fixes** subsection in `CHANGELOG.md` and the next session chronicle.
