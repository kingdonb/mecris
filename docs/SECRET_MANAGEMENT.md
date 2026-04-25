# Secret Management & Bot Security

This document outlines the secrets provided to the `mecris-bot` and the security model that allows the autonomous agent to operate with push access to the `main` branch.

## 1. Provided Secrets

The following secrets are configured in the `yebyen/mecris` repository for use in GitHub Actions:

| Secret Name | Purpose | Scope |
| :--- | :--- | :--- |
| `MECRIS_BOT_PAT` | Primary Repository Access | Fine-grained PAT with `contents:write` and `metadata:read`. Used for git operations (checkout/push). |
| `MECRIS_BOT_CLASSIC_PAT` | Legacy / API Support | A "Classic" Personal Access Token. Used by the Claude CLI for features that fine-grained PATs do not yet support (e.g., certain GraphQL queries or older API endpoints). |
| `MECRIS_BOT_ANTHROPIC_KEY` | LLM Brain (Helix) | API key for the Anthropic (or Helix proxy) endpoint. Enables the `claude` CLI to function. |
| `MECRIS_BOT_ANTHROPIC_BASE_URL` | API Routing | The base URL for the LLM provider (e.g., `https://helix.helios.corp/v1`). |

## 2. The "Safe to Run Wild" Security Model

Allowing a bot to push directly to `main` is traditionally risky. Mecris mitigates this through a multi-layered **Trust but Verify** architecture:

### A. Repository Isolation
- The bot runs exclusively on the **fork** (`yebyen/mecris`). 
- It does **not** have write access to the upstream `kingdonb/mecris` repository.
- Changes only reach the production "upstream" through human-reviewed Pull Requests.

### B. Ephemeral & Isolated Builds (SLSA L3)
- The bot operates within GitHub Actions' virtual environments, which are destroyed after every run.
- It cannot persist malicious state on the build runner.

### C. The "WASM Suit" (Hermeticity)
- All critical logic (Review Pump, Budget Governor, etc.) is compiled into **immutable WASM components**.
- The bot can modify Python source code, but the *active system* only changes when those components are re-built and re-deployed. 
- This creates a "Logical Air-Gap" between the bot's code edits and the system's operational integrity.

### D. Audit Trail
- Every commit made by the bot is clearly attributed to `mecris-bot`.
- The `mecris-bot.yml` workflow logs all turns and tool calls, providing a complete audit trail for forensic review.

## 3. Maintenance

- **PAT Expiration**: When `MECRIS_BOT_PAT` or `MECRIS_BOT_CLASSIC_PAT` expires, it must be rotated in the repository secrets.
- **Audit Requirement**: A human should periodically review the bot's commit history to ensure its autonomous decisions align with project goals.

---
*Created: 2026-04-25 | Last Updated: 2026-04-25*
