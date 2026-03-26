# Implementation Tasks

- [ ] Determine the auth mechanism for the Mecris remote (Helix deploy key vs. PAT vs. basic auth token)
- [ ] Create a bot git identity: name `mecris-bot`, email `mecris-bot@noreply` (or `mecris-bot@helix.ml`)
- [ ] Obtain or generate a scoped credential (deploy key or token) that can push to the Mecris remote only
- [ ] Write `scripts/invoke-bot.sh` — sets bot GIT_* env vars, injects the scoped credential, then launches claude CLI in the Mecris workspace
- [ ] Verify the bot can push a test commit without touching the user's personal git identity
- [ ] Document the invoke command in `CLAUDE.md` or a new `docs/BOT_AGENT.md`
- [ ] (Optional) Add a `Co-Authored-By: mecris-bot` convention to distinguish bot commits in git log
