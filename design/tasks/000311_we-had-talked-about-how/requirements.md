# Requirements: Isolated Autonomous Agent for Mecris

## Overview

Design an autonomous agent that operates with complete identity isolation from the personal user, with write access restricted to only the Mecris repository.

## User Stories

### US-1: Identity Isolation
**As** a Mecris system administrator,  
**I want** autonomous agents to operate under a dedicated bot identity,  
**so that** their commits and actions are clearly distinguishable from my personal work and cannot be attributed to me.

**Acceptance Criteria:**
- [ ] Agent commits appear as `mecris-autonomous-bot` (or similar), not as the personal user
- [ ] Agent has no access to personal SSH keys or GPG signing keys
- [ ] Agent's GitHub token is scoped to a dedicated machine account, not the user's account

### US-2: Repository Scope Restriction
**As** a security-conscious operator,  
**I want** the autonomous agent to only have push access to `kingdonb/mecris`,  
**so that** even if the agent is compromised, it cannot affect other repositories.

**Acceptance Criteria:**
- [ ] Fine-grained PAT scoped to single repository only
- [ ] No access to other repos in the GitHub account
- [ ] Agent cannot create/modify repos outside its scope

### US-3: Credential Isolation
**As** a Mecris operator,  
**I want** agent credentials stored separately from personal credentials,  
**so that** personal identity cannot be leaked through the autonomous workflow.

**Acceptance Criteria:**
- [ ] Agent credentials stored in GitHub Actions secrets or dedicated vault
- [ ] No `.env` or local credential files accessible to the agent
- [ ] Credentials injected at runtime only, never persisted in containers

### US-4: Audit Trail
**As** a system administrator,  
**I want** all autonomous agent actions to be logged and traceable,  
**so that** I can review what the agent did and when.

**Acceptance Criteria:**
- [ ] All commits include `[bot]` or similar marker in author/message
- [ ] Agent runs are logged to the `autonomous_turns` table
- [ ] Failed runs are captured with error context

## Non-Functional Requirements

- **NFR-1**: Agent must run in ephemeral containers (no persistent state on host)
- **NFR-2**: Agent must not have network access beyond GitHub API and required services
- **NFR-3**: Token lifetime should be minimized (prefer short-lived tokens where possible)

## Out of Scope

- Multi-tenancy (this is single-operator Mecris)
- Agent-to-agent communication
- Push access to any repository other than `kingdonb/mecris`
