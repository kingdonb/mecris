# Context‑Decision‑Document (CDD) for PR #6 – GitHub MCP Integration

## Context
- **Pull Request:** https://github.com/kingdonb/mecris/pull/6
- **Title:** Groq speaks #6
- **Description:** No formal description; adds markdown prompts for documentation of home‑lab infrastructure and Claude‑Code/Litellm setup.
- **Changed files (13):** New markdown prompts (`infra-docs-prompt.md`, `claude_code_man_guide.md`, etc.), updates to `docs/` (e.g., `LiteLLM_Groq_ClaudeProxy_Report.md`).
- **Goal:** Install the GitHub MCP server to enable agents to fetch PR metadata automatically.

## Decision
**Yes** – Deploy the GitHub MCP server.
- Provides programmatic access to PR details, avoiding manual WebFetch.
- Enables future agents to retrieve PR context, diffs, and reviewers automatically.
- Aligns with existing MCP integration pattern (`docs/MCP_ENDPOINTS.md`).

## Rationale
1. **Automation:** Reduces manual effort for each PR review.
2. **Consistency:** Standardizes how agents obtain external repository data.
3. **Security:** Centralized MCP can enforce access controls and audit logs.
4. **Scalability:** Supports additional MCP servers (e.g., Jira, Slack) later.

## Next Steps
- Deploy the GitHub MCP server using the existing MCP deployment scripts.
- Update `docs/MCP_INTEGRATION_SPEC.md` with endpoint configuration.
- Verify the agent can retrieve PR #6 data via the MCP API.
- Document any required secrets handling per `docs/SECRET_HANDLING_GUIDELINES.md`.

---
*Generated with Claude Code.*