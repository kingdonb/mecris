# Design: Autonomous Mecris Agent (Identity-Isolated)

## Architecture

The agent is a thin shell wrapper that:
1. Sets a bot git identity (`GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_*`)
2. Uses a scoped deploy key (SSH) or a bot PAT (HTTPS) for push access to the Mecris remote
3. Launches Claude Code (or runs a claude CLI command) with the Mecris directory as workspace
4. Has no access to the user's `~/.gitconfig`, personal SSH keys, or `.env` secrets

```
invoke-bot.sh
  └── sets GIT_* env vars (bot identity)
  └── sets GIT_SSH_COMMAND → bot deploy key
  └── launches: claude --workspace /home/retro/work/Mecris [--prompt ...]
```

## Key Decisions

### Identity isolation via environment variables, not system-wide config
Git respects `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL` env vars per-process. Setting these in the wrapper script is sufficient — no need to change the global `~/.gitconfig`.

### Deploy key (SSH) preferred over PAT (HTTPS)
A repository-scoped SSH deploy key grants push access to one repo only. A PAT tied to the user's GitHub account could be scoped to one repo but is harder to audit and revoke. Deploy key is the right primitive here.

**If Helix git (not GitHub):** The remote is `https://app.helix.ml/git/code-mecris-...`. A bot PAT or basic-auth token scoped to that remote is the equivalent — check Helix's access model.

### No personal secrets in the agent's environment
The wrapper does NOT forward `TWILIO_*`, `BEEMINDER_*`, `ANTHROPIC_API_KEY` (user's), or other personal env vars. The agent only gets what it needs to push code.

### Commit traceability
Bot commits carry `Co-Authored-By: mecris-bot <mecris-bot@noreply>` or equivalent so they are always traceable in the log without needing branch naming conventions.

## Codebase Notes

- Mecris remote: `https://app.helix.ml/git/code-mecris-1774489448`
- Mecris is a Python/FastAPI project managed with `uv`
- Existing git identity in `.git/config` has no explicit `user` section — it inherits from `~/.gitconfig`
- No existing bot/automation scripts found in `scripts/` for this purpose

## Future: Scheduling

Once the agent identity works, connecting it to a cron or Helix spin trigger is the logical next step. That is out of scope here but the wrapper script should be easy to call from cron (`0 9 * * * /path/to/invoke-bot.sh "daily maintenance"`).
