# Next Session: Cloud Restoration & TUI Polish

## Context
- **Last Session**: Token Efficiency Refactor complete. Local harness functional.
- **Current State**: 
  - Local loop is fast (<1.5k overhead).
  - Cloud sync is broken (Fermyon 404s).
  - Greek target (100 pts) is suspiciously high.

## High Priority
1. **Fix Fermyon/Spin Integration (Goal 1)**:
   - Restore the `/internal/review-pump-status-py` endpoint.
   - Address the Spin CLI 4.0 / SDK transition issues.
2. **Review Pump Logic Audit**:
   - Investigate why Greek target is pinned to 100.
   - Make targets responsive to the return pile size (e.g., 40 in pile != 100 target).
3. **TUI/UX Improvement**:
   - Model the `py_harness` interface on the polished "OpenCode" or "Claude Code" terminal experience.
   - Add color support and live-updating status bars.

## Technical Debt / Cleanup
- [ ] Remove `scripts/token_killer.py` and `scripts/caveman.py` (already moved to `attic/` or replaced by authentic versions).
- [ ] Consolidate redundant tests in `tests/`.
- [ ] Archive `mecris_usage.db` if Neon transition is 100% verified (it is).

## Notes for the Narrator
- The user had a successful walk today (0.60 miles)! Motivation is high.
- Use the **Caveman** voice for all status updates.
- **RTK** is active and should be used for all shell-intensive research.
