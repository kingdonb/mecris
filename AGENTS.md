# Mecris Agent Skills

Reusable AI agent skills for the Mecris personal accountability system.
Four skills, one loop, modeled on the Urbit Gall agent pattern.

## Skills

The Mecris agent framework is supported by a rich library of specialized skills that provide procedural guidance, automate repetitive tasks, and embed architectural knowledge directly into the agent's context.

### The Gall Loop Skills
Modeled on the Urbit Gall agent pattern, these four skills orchestrate the core development loop:

| Skill | Role | Gall arm |
|---|---|---|
| `/mecris-orient` | Read-only situation report. The battery. | `on-peek` |
| `/mecris-plan` | Write a spec issue before acting. | `on-poke` |
| `/mecris-archive` | Serialize state after work is done. | `on-save` |
| `/mecris-pr-test` | Dispatch and poll the test pipeline. | `on-agent` |

### Specialized Technical Skills
In addition to the core loop, Mecris agents have access to a suite of highly specialized technical and operational skills (provided via the integrated `kingdon-skills` repository). Trigger these using the `/` command prefix in your requests:

*   **/author-skills**: Expert procedural guidance on writing new agent skills using the standard `SKILL.md` format.
*   **/follow-leader**: Evaluates autonomous releases from `mecris-bot` and manages the canary vs. legacy-cloud version tracks.
*   **/sdd**: Guides the user and agent through Spec-Driven Development (SDD) methodology using GitHub's Spec-Kit.
*   **/atomic**: Helps create clean, atomic commits by analyzing changes and detecting mixed concerns.
*   **/tdg**: Utilizes Test-Driven Generation (TDG) techniques for Red-Green-Refactor development loops.
*   **/ticket-author**: Authors standard-format work tickets (Jira/GitHub/GitLab) with Business Value and Requirements sections.
*   **/postmortem-author**: Generates Sunkworks-style post-mortem reports with timeline reconstruction and failure pattern recognition.
*   **/start-blasting**: Pragmatic task execution for high-volume, mundane tasks (scripting vs. LLM brute-force).
*   **/hallucination-detector**: Traces claims back to source materials to validate factual assertions.
*   **/sos-emergency**: Emergency recovery procedures for Kubernetes, Talos, and Graceful Shutdowns.

**Infrastructure & Observability Skills:**
*   `/prometheus-status`, `/alertmanager-install`, `/pihole-status`, `/vind-status`, `/flux-status`, `/kubeconfig-setup`, `/crossplane-surgery`, `/github-mcp`, `/template-generate`, `/ksm-crossplane`.

## Install

### Claude Code plugin

```shell
/plugin marketplace add kingdonb/mecris
/plugin install mecris-skills@mecris
```

### Using oras

```shell
oras pull ghcr.io/kingdonb/mecris/skills:latest
```

### Manual

Copy `.github/skills/` into your project's `.claude/skills/` directory.

## The Loop

```
/mecris-orient   → situation report + recommended action
/mecris-plan     → open a spec issue (intent, because, validation)
[do the work]
/mecris-archive  → close spec, update NEXT_SESSION.md, append SESSION_LOG
/mecris-pr-test  → dispatch and poll the test pipeline for validation
```

## Integrated MCP Tools

Mecris extends the agent's capabilities with over 50 distinct MCP (Model Context Protocol) tools, bridging the gap between natural language and the underlying infrastructure, databases, and third-party APIs.

### Mecris Core Context & Accountability Tools
*   **Strategic Context**: `mcp_mecris_get_narrator_context`, `mcp_mecris_get_system_health`, `mcp_mecris_get_coaching_insight`
*   **Goal Mastery (Beeminder)**: `mcp_mecris_get_beeminder_status`, `mcp_mecris_get_daily_activity`, `mcp_mecris_send_beeminder_alert`, `mcp_mecris_get_daily_aggregate_status`, `mcp_mecris_add_goal`, `mcp_mecris_complete_goal`
*   **Language Learning**: `mcp_mecris_get_language_velocity_stats`, `mcp_mecris_set_review_pump_lever`, `mcp_mecris_trigger_language_sync`
*   **Budget & Usage**: `mcp_mecris_get_budget_status`, `mcp_mecris_get_unified_cost_status`, `mcp_mecris_get_budget_governor_status`, `mcp_mecris_get_recent_usage`, `mcp_mecris_record_usage_session`, `mcp_mecris_get_real_anthropic_usage`, `mcp_mecris_record_groq_reading`, `mcp_mecris_get_groq_status`
*   **Scheduling & Comms**: `mcp_mecris_get_scheduler_queue`, `mcp_mecris_enqueue_message`, `mcp_mecris_trigger_reminder_check`, `mcp_mecris_set_notification_prefs`
*   **Knowledge Retrieval**: `mcp_mecris_ask_mecris`, `mcp_mecris_search_bookmarks`, `mcp_mecris_get_bookmarks_by_topic`, `mcp_mecris_get_weather_report`
*   **Data Portability (GDPR)**: `mcp_mecris_export_user_data`, `mcp_mecris_delete_user_data`

### GitHub Integration Tools
The environment automatically provides full GitHub repository access via the GitHub MCP server:
*   **Code & Files**: `mcp_github_get_file_contents`, `mcp_github_create_or_update_file`, `mcp_github_push_files`, `mcp_github_search_code`
*   **Issues**: `mcp_github_list_issues`, `mcp_github_get_issue`, `mcp_github_create_issue`, `mcp_github_update_issue`, `mcp_github_add_issue_comment`, `mcp_github_search_issues`
*   **Pull Requests**: `mcp_github_list_pull_requests`, `mcp_github_get_pull_request`, `mcp_github_create_pull_request`, `mcp_github_get_pull_request_files`, `mcp_github_create_pull_request_review`, `mcp_github_merge_pull_request`, `mcp_github_get_pull_request_status`, `mcp_github_update_pull_request_branch`
*   **Git Ops**: `mcp_github_create_branch`, `mcp_github_list_commits`, `mcp_github_search_repositories`, `mcp_github_fork_repository`, `mcp_github_search_users`

## Update

```shell
/plugin update mecris-skills@mecris
```

Or pull the latest OCI artifact:

```shell
oras pull ghcr.io/kingdonb/mecris/skills:latest
```
