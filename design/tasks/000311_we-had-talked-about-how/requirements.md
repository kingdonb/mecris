# Requirements: Isolated Autonomous Agent for Mecris

## Overview

This document describes the requirements for an autonomous agent that operates with complete identity isolation from the personal user. The implementation is **already complete** and operational as `mecris-bot` running on `yebyen/mecris`.

## Threat Model: Supply Chain Attacks

### The LiteLLM Incident (March 2026)

A popular Python package (`litellm`) on PyPI was backdoored to steal credentials and auth tokens. This is the attack we're defending against:

1. Developer runs `pip install` or upgrades dependencies
2. Compromised package executes malicious code during install/import
3. Malware exfiltrates SSH keys, API tokens, browser cookies
4. Attacker gains access to all services the developer is authenticated to

### Why This Matters for Mecris

If autonomous agents run with personal credentials on a personal machine:
- Compromised dependency could steal `kingdonb`'s GitHub token
- Attacker could push malicious code to any repo `kingdonb` has access to
- Personal SSH keys, work credentials at risk

### Solution: Identity Isolation

Run autonomous agents under a separate identity (`yebyen`) with:
- Credentials scoped to only the bot's fork
- No access to personal repos or work repos
- Human review gate (PR process) before code reaches trusted repo

## User Stories

### US-1: Identity Isolation ✅ IMPLEMENTED

**As** a Mecris system administrator,  
**I want** autonomous agents to operate under a dedicated bot identity,  
**so that** their commits cannot be attributed to me and compromise of the bot doesn't affect my personal accounts.

**Acceptance Criteria:**
- [x] Agent commits appear as `mecris-bot`, not as personal user
- [x] Agent operates from `yebyen/mecris` fork, not `kingdonb/mecris`
- [x] Agent has no access to personal SSH keys or GPG keys
- [x] Agent's GitHub token is scoped to `yebyen/mecris` only

### US-2: Repository Scope Restriction ✅ IMPLEMENTED

**As** a security-conscious operator,  
**I want** the autonomous agent to only have push access to `yebyen/mecris`,  
**so that** even if the agent is compromised, it cannot affect other repositories.

**Acceptance Criteria:**
- [x] Fine-grained PAT scoped to `yebyen/mecris` only
- [x] No access to `kingdonb/mecris` except via public PR process
- [x] No access to other repos under either account

### US-3: Human Review Gate ✅ IMPLEMENTED

**As** a Mecris operator,  
**I want** all autonomous changes to require human review before reaching the trusted repo,  
**so that** malicious or incorrect changes can be caught before they're trusted.

**Acceptance Criteria:**
- [x] Bot pushes to `yebyen/mecris:main` directly
- [x] Bot opens PRs to `kingdonb/mecris` for human review
- [x] Human reviews PRs using Gemini agent (per `GEMINI.md`)
- [x] Changes only reach `kingdonb/mecris` after explicit approval

### US-4: Audit Trail ✅ IMPLEMENTED

**As** a system administrator,  
**I want** all autonomous agent actions to be logged and traceable,  
**so that** I can review what the agent did and when.

**Acceptance Criteria:**
- [x] All commits have clear bot identity (`mecris-bot`)
- [x] GitHub Actions logs capture full execution trace
- [x] `session_log.md` documents each bot run
- [x] PR history shows all changes proposed by bot

### US-5: Prevent Upstream Workflow Failures ⏳ IN PROGRESS

**As** a repository maintainer,  
**I want** the `mecris-bot.yml` workflow to not run on `kingdonb/mecris`,  
**so that** I don't have 8 failed workflow runs per day cluttering my Actions history.

**Acceptance Criteria:**
- [ ] Workflow includes `if: github.repository == 'yebyen/mecris'` condition
- [ ] Scheduled runs on `kingdonb/mecris` skip the job entirely
- [ ] No more daily failures on upstream repo

## Non-Functional Requirements

- **NFR-1**: Agent runs in ephemeral GitHub Actions runners (no persistent state) ✅
- **NFR-2**: Agent uses Helix API for Claude access (separate from personal Anthropic key) ✅
- **NFR-3**: Bot operates on schedule (8x/day, US Eastern hours) without human intervention ✅

## Out of Scope

- Multi-tenancy (this is single-operator Mecris)
- Direct push access to `kingdonb/mecris` by bot
- Automated PR merging (human review required)