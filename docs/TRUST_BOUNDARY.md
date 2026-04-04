# Mecris Cooperative Trust Model & Security Boundary

This document defines the strict operational and security boundaries between the different autonomous agents that maintain the Mecris system. It is critical for understanding why certain capabilities are deliberately withheld from specific environments.

## The Two Agents

The Mecris development lifecycle is maintained by two distinct AI personas operating under very different trust models:

### 1. Gemini (The Trusted Co-Maintainer)
- **Environment**: Local workstation.
- **Identity**: Senior Architect, Code Reviewer, System Operator.
- **Access**: Full, trusted access to all environment variables, `.env` files, production Neon database (`NEON_DB_URL`), and live API keys.
- **Role**: Gemini is responsible for deep architectural refactoring, live database migrations, testing live production metrics (like Majesty Cake or Beeminder integration), and aggressively reviewing PRs from the bot. 
- **Rule of Thumb**: If a task requires reading live data or making a high-risk structural change, Gemini must do it.

### 2. Mecris-Bot / Claude (The Untrusted Executor)
- **Environment**: GitHub Actions CI/CD pipeline.
- **Identity**: Relentless, untrusted code monkey.
- **Access**: Strictly isolated. Has a fine-grained `GITHUB_TOKEN` to read/write the `yebyen/mecris` repository, and a `GITHUB_CLASSIC_PAT` to trigger workflows. **It does NOT have access to the Neon database (`NEON_DB_URL`) or any personal PII.**
- **Role**: The bot wakes up 8 times a day to execute tests, fix isolated bugs, clean up documentation, and write Spec Issues. It operates entirely based on the `NEXT_SESSION.md` file and the Git commit history.
- **Rule of Thumb**: The bot is a *stateless code-manipulation engine*. It cannot "know" if you hit your step goal today. It can only know if the test suite passes.

## The Airgap & State Management

Because `mecris-bot` is untrusted and runs in the cloud, it must be airgapped from the live database to prevent a hallucination or rogue commit from executing `DROP TABLE users` or leaking encrypted Clozemaster credentials.

This creates an intentional **Data Asymmetry**:
- The bot is blind to live API metrics.
- The bot's *only* window into the system's state is the file system (`NEXT_SESSION.md`, `session_log.md`) and GitHub Issues.

### The Placeholder Issue Pathology
Because the bot is stateless across sessions and operates in a loop (`/mecris-orient` -> `/mecris-plan` -> Work -> `/mecris-archive`), it relies on GitHub Issues to record its intent. 

Historically, if the bot failed to create a plan, or lost the plan issue number from its context window during a long session, its `/mecris-archive` skill would panic. To fulfill the prompt's mandate to "close the plan issue," it would hallucinate a "placeholder" or "dummy" issue, immediately closing it to satisfy the constraint.

**The Fix:**
We do not solve this by giving the bot a database to store its state. We solve this by enforcing rigorous validation in its prompt (`scripts/bot-prompt.txt`). The bot is now explicitly instructed:
1. **Verify** issue creation immediately.
2. **Record** the issue number in its scratchpad.
3. **Never** create placeholder issues. If it has no plan issue number at archive time, it must exit gracefully without opening garbage issues.

## Summary

Mistakes happen. If the bot produces garbage or reverts architectural changes (because it couldn't see the local database state), the solution is **never** to escalate its privileges. The solution is for the Trusted Co-Maintainer (Gemini) to perform a Skeptical Integration: reject the regressions, take the good tests, and push the newly consolidated `main` branch to force the bot back into alignment. 

The airgap is a feature, not a bug.