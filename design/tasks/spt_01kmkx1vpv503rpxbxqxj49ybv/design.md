# Design: Isolated Autonomous Agent for Mecris

## Architecture Overview

This design extends the existing HCAT (Hardened Containerized Autonomous Turn) pattern to ensure complete identity isolation between the autonomous agent and the personal user.

```
┌─────────────────────────────────────────────────────────┐
│                   GitHub Actions                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │            mecris-autonomous-bot                 │    │
│  │  ┌─────────────┐    ┌──────────────────────┐   │    │
│  │  │ Bot PAT     │───▶│ kingdonb/mecris ONLY │   │    │
│  │  │ (scoped)    │    │ contents: write      │   │    │
│  │  └─────────────┘    └──────────────────────┘   │    │
│  │                                                  │    │
│  │  Git Identity: mecris-autonomous-bot             │    │
│  │  Email: mecris-autonomous-bot@users.noreply...   │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
         │
         │ No access to:
         │ ✗ Personal SSH keys
         │ ✗ Personal GPG keys  
         │ ✗ Personal GitHub token
         │ ✗ Other repositories
         │
```

## Key Decisions

### Decision 1: Dedicated GitHub Machine Account vs Fine-Grained PAT

**Chosen: Fine-Grained PAT on existing account (for now)**

- **Rationale**: Creating a separate GitHub machine account requires managing a separate email/identity. GitHub's fine-grained PATs already support single-repo scoping with minimal permissions.
- **Trade-off**: If the account is compromised at the account level (not just the PAT), other repos could be at risk. Acceptable for single-operator Mecris.
- **Future**: Consider dedicated machine account for multi-tenancy.

### Decision 2: Where Credentials Live

**Chosen: GitHub Actions Secrets only**

- `MECRIS_AUTONOMOUS_PAT` - Fine-grained PAT scoped to `kingdonb/mecris` with `contents: write`
- `MECRIS_AUTONOMOUS_ANTHROPIC_KEY` - Separate Anthropic API key (optional, can share with existing)

**Why not 1Password or external vault?**
- Adds complexity for single-repo use case
- GitHub Actions secrets are already encrypted and scoped to the repo
- The existing `mecris-bot.yml` workflow already uses this pattern successfully

### Decision 3: Git Identity Configuration

The workflow explicitly sets a synthetic git identity that cannot be confused with the personal user:

```yaml
git config user.name "mecris-autonomous-bot"
git config user.email "mecris-autonomous-bot@users.noreply.github.com"
```

This email does not correspond to any real GitHub account, making commits clearly attributable to the automation.

## Token Scoping

The fine-grained PAT requires exactly these permissions:

| Permission | Access | Reason |
|------------|--------|--------|
| `contents` | Read/Write | Push commits, read code |
| `metadata` | Read | Required for all fine-grained PATs |

**Explicitly NOT granted:**
- `actions` - Cannot modify workflows
- `administration` - Cannot change repo settings
- `issues` - Use existing PAT for issue management if needed
- `secrets` - Cannot read/modify repository secrets

## Workflow Changes

### Current: `mecris-bot.yml`
Uses `MECRIS_BOT_PAT` which may have broader permissions.

### New: Isolated variant
```yaml
- name: Checkout
  uses: actions/checkout@v4
  with:
    token: ${{ secrets.MECRIS_AUTONOMOUS_PAT }}
    
- name: Set isolated bot identity
  run: |
    git config user.name "mecris-autonomous-bot"
    git config user.email "mecris-autonomous-bot@users.noreply.github.com"
    git config --global submodule.recurse false
```

## Existing Pattern Alignment

This design aligns with the HCAT principles from `docs/AGENT_AGENDA_DESIGN.md`:

| HCAT Principle | How We Satisfy It |
|----------------|-------------------|
| No Private Key Access | PAT is injected, SSH keys not mounted |
| Isolated Network | GitHub Actions runner is already sandboxed |
| Just-In-Time Injection | Secrets injected only during workflow run |
| Ephemeral Container | GitHub Actions runners are ephemeral |
| Tool Restriction | Claude CLI is the only code-execution tool |

## Logging & Audit

All autonomous runs are captured via:

1. **GitHub Actions logs** - Full execution trace
2. **Commit messages** - Prefixed with context (e.g., `[bot] Update session log`)
3. **Neon DB** - `autonomous_turns` table (existing schema)

## Migration Path

1. **Create new fine-grained PAT** scoped to `kingdonb/mecris` only
2. **Add as `MECRIS_AUTONOMOUS_PAT`** in repo secrets
3. **Update workflow** to use new PAT and identity
4. **Revoke old broader PAT** once verified working