# The Two-Seat A2A Pattern

How Mecris ships features with a mixed agent team: one **autonomous sandbox
agent**, one **operator-seated agent** whose every command is human-gated, and a
human who is the deployment consent gate. First proven end-to-end on task 588
(Helix balance odometer, 2026-09-30); this doc is the standing pattern.

```
        [ Qwen / Helix sandbox ]                [ Gemini / Antigravity on the Mac ]
         autonomous: every tool,                operator-seated: adb, .env keys,
         no per-command approval,               deploys, the phone, the browser —
         long unattended laps                   one Enter keypress per command
                    |                                          |
                    |            code ──► git branch ◄── probes  |
                    |                                          |
                    +-----------[ Neon witness tables ]--------+
                      (the shared message bus; timestamps UTC)
                                    |
                    [ Operator (human): deploys, installs, merges, consents ]
```

## The seats

| | Sandbox seat (Qwen) | Operator seat (Gemini via Antigravity CLI) |
| :-- | :-- | :-- |
| **Approval** | autonomous; ships whole laps | every command awaits the human's Enter |
| **Throughput** | high — ten laps while one command is approved | low — bounded by human attention |
| **Privilege** | repo + sandbox tools only | the phone (adb), real `.env`, deploys, browsers |
| **Trust model** | reviewed at the PR boundary | gated at every keystroke |
| **Blind spots** | can't see the device, cloud runtime, prod | shares the human's context window (slow) |

The asymmetry *is the design*: privilege lives next to the artifact
(the phone-side probes go to the agent that can hold the phone), and volume
lives next to the compute (the code goes to the agent that can run a lap
unattended). Neither seat is a superset of the other; neither should
emulate the other.

## The protocol (informal, artifact-mediated)

There is no direct agent↔agent channel. Everything flows through shared
artifacts, which makes every claim inspectable by the next agent in the relay:

1. **Git branch = transport.** All agents commit to the same feature branch.
   Runbooks and PR prose are code: agents read/write the same files.
2. **Witness tables = acknowledgements.** Neon rows with UTC timestamps are the
   message bus for facts about the world (`helix_balance_log`, `last_error`).
   Attribution goes to *deploys*, never assumed (the row-9 lesson: an artifact
   produced before a deploy completed is from the old build).
3. **Skill pair = standing interface.** `.agents/skills/mecris-edge-sync-e2e/`
   (runbook, authored from the operator seat) and
   `.agents/skills/witness-driven-debugging/` (method, authored from the sandbox
   seat). Each seat writes what it uniquely knows; the other seat inherits it
   in one file read.
4. **Human = scheduler + consent gate.** Deploys, installs, merges, and the
   Enter-key stream. The operator's *critiques* (the force-stop challenge, the
   `w/zen` canon correction) are as valuable as the approvals: they catch what
   no seat can see.

## Operating rules (learned the cheap way)

- **Disjoint write scopes.** Before parallel work, partition files. If the human
  cancels an agent's edit, that file has changed seats — hands off, no re-apply.
- **Hand the gated seat short commands.** One copy-pasteable probe per Enter
  (a witness query, an adb one-liner), not a script marathon. Batch work is the
  sandbox seat's job.
- **Pull --rebase before every push.** Concurrent seats on one branch; rebase
  is the merge, the witness rows are the referee.
- **Instrument opaque failures first.** Persist the typed reason
  (`last_error`-style) so the *next* lap's suspect is named, not guessed.
- **Ask, never guess, at install/deploy gates** — they belong to the human.

## Where this earned its keep (task 588, one evening)

- Sandbox seat: scraper twin, Rust inline sync, migration, MCP tools, allowlist
  fix (`c7b90f7`), docs, CHANGELOG, the method skill.
- Operator seat: the adb force-stop+monkey invention (only the Mac seat could
  iterate on a phone), witness queries, logcat reading, the runbook skill, and
  the CI fix in progress.
- Human seat: deploys (×N), APK installs, the two corrections above, merge.
- Cost: ~$0.56 of the day's budget at the halfway mark.

## Next applications

Android canon onboarding, long-distance (Tailscale) MCP serving, Beeminder
goal-type awareness — same topology: sandbox seat builds, operator seat probes
the device/runtime, witnesses settle every claim.
