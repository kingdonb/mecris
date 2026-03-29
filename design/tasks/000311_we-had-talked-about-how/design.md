# Design: Isolated Autonomous Agent for Mecris

## Executive Summary

This design documents the **existing** mecris-bot implementation that provides identity-isolated autonomous agent capabilities for the Mecris accountability system. The bot operates on `yebyen/mecris` (the fork) with credentials completely separate from the personal identity (`kingdonb`), enabling safe autonomous operation with limited blast radius.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     kingdonb/mecris (upstream)                   │
│                     Personal identity repo                       │
│                     - Human reviews PRs                          │
│                     - No bot credentials                         │
│                     - mecris-bot.yml runs but skips (no secrets) │
└───────────────────────────────▲──────────────────────────────────┘
                                │ Pull Requests
                                │ (public, anyone can open)
┌───────────────────────────────┴──────────────────────────────────┐
│                      yebyen/mecris (fork)                         │
│                      Bot identity repo                            │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    mecris-bot workflow                       │ │
│  │  • MECRIS_BOT_PAT (fine-grained, yebyen/mecris only)        │ │
│  │  • MECRIS_BOT_CLASSIC_PAT (repo scope, for cross-repo PRs)  │ │
│  │  • MECRIS_BOT_ANTHROPIC_KEY (Helix API token)               │ │
│  │  • Git identity: mecris-bot / mecris-bot@noreply             │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

## Threat Model: Supply Chain Attacks (LiteLLM Incident)

The primary threat we're defending against is **supply chain compromise** of dependencies, as demonstrated by the March 2026 LiteLLM PyPI backdoor incident where a popular Python package was modified to steal credentials and auth tokens.

### Attack Scenario

1. Developer runs `pip install` or `uv sync` on their personal machine
2. A compromised package executes malicious code during install or import
3. Malware exfiltrates SSH keys, API tokens, browser cookies, etc.
4. Attacker gains access to all services the developer is authenticated to

### Why Identity Isolation Matters

If the autonomous agent (mecris-bot) runs with personal credentials:
- Compromised dependency in CI could steal `kingdonb`'s GitHub token
- Attacker could push to any repo `kingdonb` has access to
- Personal identity (SSH keys, GPG keys) could be exfiltrated

With isolated identity (`yebyen`):
- Bot only has access to `yebyen/mecris`
- Even if compromised, blast radius is limited to one fork
- Personal repos, work repos remain protected
- Human review gate (PR to `kingdonb/mecris`) catches malicious changes

## Current Implementation

### Workflow: `.github/workflows/mecris-bot.yml`

The workflow runs on `yebyen/mecris` only and:

1. **Validates Helix API key** before running Claude CLI
2. **Sets bot git identity** (not linked to any real GitHub account)
3. **Runs Claude Code CLI** with `--dangerously-skip-permissions`
4. **Pushes directly to `yebyen/mecris:main`**
5. **Opens PRs to `kingdonb/mecris`** using classic PAT (public action, no special access needed)

### Credential Scoping

| Secret | Type | Scope | Purpose |
|--------|------|-------|---------|
| `MECRIS_BOT_PAT` | Fine-grained PAT | `yebyen/mecris` only | Checkout, push |
| `MECRIS_BOT_CLASSIC_PAT` | Classic PAT | `repo` scope | Open PRs cross-repo |
| `MECRIS_BOT_ANTHROPIC_KEY` | Helix API key | Claude API access | Run Claude CLI |

### Git Identity

```yaml
git config user.name "mecris-bot"
git config user.email "mecris-bot@noreply"
```

This email is synthetic - it doesn't correspond to any GitHub account, making commits clearly attributable to automation.

## Key Design Decisions

### Decision 1: Fork-based isolation vs. Branch protection

**Chosen: Separate fork (yebyen/mecris)**

- Complete credential isolation - different GitHub account
- No risk of accidental secret leakage to upstream
- Clear audit trail (all bot commits come from fork)
- Human review gate via PR process

### Decision 2: Fine-grained PAT vs. Deploy key

**Chosen: Fine-grained PAT scoped to single repo**

- GitHub fine-grained PATs can be scoped to exactly one repository
- Easier to rotate than deploy keys
- Works with standard `actions/checkout`

### Decision 3: Prevent upstream workflow failures

**Issue identified**: `mecris-bot.yml` runs on schedule in `kingdonb/mecris` but fails due to missing secrets (8 failures/day cluttering Actions history).

**Fix**: Add job condition to skip on upstream:

```yaml
jobs:
  run-bot:
    if: github.repository == 'yebyen/mecris'
```

## Alignment with HCAT Principles

This implementation follows the HCAT (Hardened Containerized Autonomous Turn) principles from `docs/AGENT_AGENDA_DESIGN.md`:

| Principle | Implementation |
|-----------|----------------|
| No Private Key Access | Bot has no access to `kingdonb`'s SSH/GPG keys |
| Isolated Network | GitHub Actions runner is sandboxed |
| Just-In-Time Injection | Secrets injected only during workflow |
| Ephemeral Container | GitHub Actions runners are ephemeral |
| Blast Radius Limitation | Bot can only affect `yebyen/mecris` |
| Human Yield | PRs require human review before merge |

## Operational Flow

```
1. mecris-bot runs on schedule (8x/day) in yebyen/mecris
2. Bot executes /mecris-orient → /mecris-plan → work → /mecris-archive
3. Bot pushes commits directly to yebyen/mecris:main
4. Bot opens PR from yebyen/mecris to kingdonb/mecris
5. Kingdon (human) reviews PR using Gemini agent (GEMINI.md instructions)
6. If approved, Kingdon merges to kingdonb/mecris
7. Code is now in the "trusted" upstream repo
```

## Security Properties

✅ **Identity Isolation**: Bot identity (`yebyen`) separate from personal (`kingdonb`)  
✅ **Repository Isolation**: Bot can only push to `yebyen/mecris`  
✅ **Credential Isolation**: Bot secrets stored only in fork, not upstream  
✅ **Human Review Gate**: All changes require PR approval  
✅ **Audit Trail**: Clear separation of bot vs. human commits  
✅ **Limited Blast Radius**: Compromise of bot affects only fork  
