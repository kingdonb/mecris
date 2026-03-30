# 👻 Agent Agenda: Presence, Free Will, and the Autonomous Continuum

## 1. Vision
Transform Mecris from a reactive toolset into a proactive cognitive system. This design enables agents to wake up autonomously, execute mission-critical maintenance, and maintain the "narrative thread" without direct human intervention, while strictly respecting daily token quotas and security boundaries.

## 2. The Continuum of Presence
The system's "Presence" is defined by its ability to access LLM reasoning and local system tools.

| State | Name | Context | Reasoning Power | Description |
|-------|------|---------|-----------------|-------------|
| **LUCID** | Interactive | Workstation Awake + Human Present | High (Full CLI access) | The human is actively driving the agent. |
| **DREAMING** | Autonomous | Workstation Awake + Human Away | Medium (Headless Loopback) | The system spawns "Ghost Sessions" to perform background work. |
| **DARK** | Failover | Workstation Asleep / Remote Only | Low (None) | System relies on stateless Rust/Go Spin workers and Neon DB heartbeats. |

## 3. The "Ghost Session" Loopback: Hardened Containerized Autonomous Turn (HCAT)
To leverage Google One AI Pro and Copilot subscriptions for autonomous work without exposing the host system, Mecris utilizes ephemeral, isolated containers.

### Mechanism:
1. **Trigger**: The `MecrisScheduler` (Python) identifies an agenda window.
2. **Locking**: Checks for `presence.lock` to ensure no human is currently using the CLI.
3. **Container Spawn**: Launches a fresh, hardened container based on an **explicitly pinned image digest** (no `:latest` tags).
4. **Execution**: The agent runs within the container in a TTY-aware loopback:
   - **Gemini**: `gemini --prompt "AGENDA_PROMPT" --yolo`
   - **Copilot**: `gh copilot -p "AGENDA_PROMPT" --allow-tool "Bash(*)"`
5. **Recording**: The turn is captured, summarized, and logged to the `autonomous_turns` table in Neon.
6. **Destruction**: The container is immediately destroyed upon completion, leaving zero state on the host.

## 4. Free Will: The Quota and Blast Radius System
To prevent infinite loops, budget exhaustion, or unauthorized data access, "Free Will" is strictly sandboxed.

- **Token Bank**: A daily allowance of 5-10 autonomous turns.
- **Priority Auction**: If multiple agendas are due, the system selects based on the `urgent_items` in the Narrator Context.
- **Circuit Breaker**: If a container exceeds 5 minutes or 10 tool calls, it is killed by the host monitor.
- **Blast Radius Limitation**: 
    - **No Host Mounts**: Containers have no access to the host filesystem outside of an ephemeral work-directory.
    - **Read-Only Code**: The core system files are mounted as read-only; agents can only propose changes via git patches or specific tool-gates.
    - **Isolated Network**: Containers are on a restricted Docker network with no access to local LAN services.

## 5. The Three-Agent Agenda (Constructive Interference)

### A. The Archivist (Gemini-led)
- **Role**: Memory and Thread Maintenance.
- **Task**: Summarizes the last 24h of session logs, reconciles GitHub Issues with `TODO.md`, and updates `NEXT_SESSION.md`.
- **Frequency**: Every morning @ 08:00.

### B. The Auditor (Copilot-led)
- **Role**: Rigor and Finances.
- **Task**: Scrapes latest billing data, reconciles `UsageTracker` drift, and performs minor technical debt refactors (linting, doc updates).
- **Frequency**: Every mid-day @ 13:00.

### C. The Narrator (Gemini-led)
- **Role**: Accountability and Human Connection.
- **Task**: Evaluates walk status and language debt. Writes the "Victory Log" or decides the "Nag Ladder" escalation for the following morning.
- **Frequency**: Every evening @ 18:00.

## 6. Security & Supply Chain Hardening (The LiteLLM Post-Mortem)
To prevent authorized access or malicious tool use, and especially to mitigate "poisoned" package attacks, Mecris implements a multi-layer security model.

### A. Strict Pinning & Supply Chain Integrity
- **Base Images**: All Dockerfiles use specific SHA256 digests. No `:latest` tags permitted.
- **Unscoped SHA Warning**: Be aware of "unscoped" SHAs—where a platform (like GitHub) resolves a commit hash across forks of a repo. A pinned SHA must be verified to exist in the *primary* trusted repository, not just any fork. See [The Comforting Lie of SHA-pinning](https://www.vaines.org/posts/2026-03-24-the-comforting-lie-of-sha-pinning/) for the full threat analysis.
- **Dependencies**: Python environments are strictly managed by `uv.lock` with hashes verified. `pip install` without a lockfile is forbidden in autonomous contexts.
- **The Update Queue**: New releases of LLM libraries or base images are never pulled automatically. 
- **Approval Flow**: The Archivist may detect a new version and log it, but the actual update must be performed during a **LUCID** (interactive) session by the human.

### B. Secret Management
- **Centralized Vault**: Gemini and GitHub/Copilot auth tokens are stored in a dedicated Secret Manager (e.g., AWS Secrets Manager or 1Password).
- **Just-In-Time Injection**: Tokens are injected into the container environment only for the duration of the turn. They are never stored in the image or on the host disk.
- **Agent-Specific Scopes**: Each agent uses a restricted service account/token with minimal permissions.

### C. Execution Sandbox (HCAT)
- **TTY-aware Runner**: Spawns inside a transient `tmux` or `pty` environment within the container to satisfy CLI requirements.
- **Tool Restriction**: The `--allow-tool` flag is strictly limited per agenda (e.g., The Archivist cannot use `run_shell_command` outside of `git`).
- **No Private Key Access**: Autonomous agents can edit code but are explicitly denied read access to `.env` or SSH keys via filesystem-level protections and container isolation.

### D. Human Yield
- If any human interaction is detected (keyboard input or session start), the `presence.lock` is released and the Ghost Session is terminated immediately.

## 7. Implementation Path
1. [ ] **`bin/mecris presence`**: Add logic to detect if human is active.
2. [ ] **Neon Schema**: Add `autonomous_turns` and `token_bank` tables.
3. [ ] **HCAT Container Definition**: Create SHA-pinned Dockerfile for autonomous agents.
4. [ ] **Secret Manager Integration**: Implement a generic `SecretProvider` class for token injection.
5. [ ] **TTY-aware Runner**: Develop a Python helper to safely execute `gemini/gh copilot` in a virtual terminal within the container.
6. [ ] **Scheduler Integration**: Map the 3 agendas to `MecrisScheduler`.
