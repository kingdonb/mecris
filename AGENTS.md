# Mecris Agent Skills

Reusable AI agent skills for the Mecris personal accountability system.
Four skills, one loop, modeled on the Urbit Gall agent pattern.

## Skills

| Skill | Role | Gall arm |
|---|---|---|
| `/mecris-orient` | Read-only situation report. The battery. | `on-peek` |
| `/mecris-plan` | Write a spec issue before acting. | `on-poke` |
| `/mecris-archive` | Serialize state after work is done. | `on-save` |
| `/mecris-pr-test` | Dispatch and poll the test pipeline. | `on-agent` |

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
/mecris-orient  → situation report + recommended action
/mecris-plan    → open a spec issue (intent, because, validation)
[do the work]
/mecris-archive → close spec, update NEXT_SESSION.md, append SESSION_LOG
```

## Update

```shell
/plugin update mecris-skills@mecris
```

Or pull the latest OCI artifact:

```shell
oras pull ghcr.io/kingdonb/mecris/skills:latest
```
