# Next Session: The Lab of Excellence — Budget Governor (#144) 🏛️

## Current Status (2026-03-29)
- **Synced and Merged**: kingdonb/mecris#150, #151, and #152 are all merged and synchronized. Upstream `main` and `yebyen/main` are now fully in sync.
- **Greek Backlog Booster**: Successfully implemented and verified with 8/8 tests. 
- **Arabic Heuristic**: Conservative `/16` divisor is now in place in `services/review_pump.py`.
- **Coaching Lowercase Key Bug FIXED**: `coaching_service.py` now uses `"arabic"` and `"greek"` matching `get_language_stats()` lowercase output. This restored multiplier-driven lever pressure that was silently broken.
- **94+ Tests Pass**: The suite is stable and green.

## Verified This Session
- [x] Identity Check: 🏛️ Canary active.
- [x] Greek Backlog Booster (#129) implemented and merged.
- [x] Arabic early-switch bug (#151) fixed via `/16` heuristic and closed.
- [x] Coaching lowercase key bug (#24) fixed and verified with 9 coaching tests.
- [x] kingdonb/mecris#152 merged and repos synchronized.

## Pending Verification (Next Session)
- **Identity Check**: 🏛️ (Must appear in session_log.md).
- **Primary Objective: Budget Governor (Issue #144)**:
    - This is a high-autonomy "Lab of Excellence" task. Take your time.
    - **MUST READ:** 👉 `docs/BUDGET_GOVERNOR_GUIDANCE.md` for architectural hints and the Helix API secret.
    - **Goal**: Implement the `BudgetGovernor` class to manage multi-bucket quotas (Anthropic, Groq, Helix, Gemini).
    - **The Rule**: 5% Daylight Window (approx 39m) → no more than 5% of any bucket's period quota.
    - **Helix Inversion**: Active encouragement to *spend* Helix/Gemini free credits, rather than ration them.
    - **Location**: Create a new module `services/budget_governor.py`. Do NOT stuff into `usage_tracker.py`.
    - **Output**: A new MCP tool `/mecris-budget` that reports routing decisions.
- **Field discovery**: (Still blocked, human-only).
- **Secondary Backlog**: Issue #122 (Android multiplier race) if #144 is fully spec'd.

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris is the bot's working fork; kingdonb/mecris is the upstream. **Sync via PR only when work is a "Polished Gem."**
- Bot governor: 80 turns documented limit. Planning (mecris-plan) and TDG are mandatory before code changes.
- Session log at `session_log.md`.
- `ARABIC_POINTS_PER_CARD = 16` is the single source of truth (in `services/review_pump.py`).
- `get_language_stats()` always stores keys as `row[0].lower()` — all code consuming lang_stats must use lowercase keys.
