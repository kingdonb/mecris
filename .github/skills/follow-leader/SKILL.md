---
name: follow-leader
description: 'Manage tracking, evaluating, and adopting autonomous releases from mecris-bot, deciding when to sunset legacy tracks. Trigger with /follow-leader'
allowed-tools: ['read_file', 'run_shell_command', 'mcp_github_list_pull_requests', 'mcp_github_get_pull_request']
---

# Follow Leader Release Management

I act as the strategic evaluator for autonomous releases published by `mecris-bot`, tracking when to follow its vanguard, manage parallel versions (canary vs. legacy), and sunset old releases.

## When I Activate
- "Review bot releases"
- "Update legacy vs canary tracks"
- "Sunset spin 3 compatibility"
- Trigger with `/follow-leader`

## Core Capabilities
1. Identify and evaluate new autonomous releases or pull requests from `mecris-bot`.
2. Map changes against our parallel versioning strategy (e.g., `main` canary vs. `legacy-cloud` shim).
3. Recommend whether to follow the bot's vanguard changes, diverge to maintain legacy stability, or both.
4. Execute decisions to prune or sunset legacy branches when the infrastructure gap closes.

## The Bifurcated Release Strategy
When infrastructure (like Spin v3 vs. v4) enforces constraints that the bot has moved past:
- **Canary Track (`main`)**: Follow the bot. Test bleeding-edge changes in local/sandbox environments.
- **Legacy Track (`legacy-cloud`)**: Maintain pragmatic shims. Backport fixes where necessary but heavily gate merging bleeding-edge bot changes here.
- **Sunsetting**: Legacy tracks are not permanent. When the ecosystem catches up, we sunset the shim and unify on `main`.

## Expected Failure Modes

| Failure Mode | Symptoms | Workaround |
|--------------|----------|------------|
| Incompatible ABI merge | Spin v4 consumer crashes on Spin v3 host | Revert on `legacy-cloud`; rely on negative E2E test. |
| Divergent Histories | Merge conflicts backporting to legacy | Manually resolve or rewrite async/sync logic as needed. |
| Missing Bot PRs | No updates from `mecris-bot` | Check token expiration or bot failure state. |

## Slash Command

### `/follow-leader`
Runs the autonomous evaluation workflow:
1. Checks for new releases or PRs from `mecris-bot`.
2. Cross-references the changes against the current active branches (`main`, `legacy-cloud`).
3. Proposes an update and tagging strategy (e.g., `v0.1.0-canary` vs `v0.0.1`).