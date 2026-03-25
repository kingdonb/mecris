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

## 3. The "Ghost Session" Loopback
To leverage Google One AI Pro and Copilot subscriptions for autonomous work, Mecris utilizes "Command-Line Inception."

### Mechanism:
1. **Trigger**: The `MecrisScheduler` (Python) identifies an agenda window.
2. **Locking**: Checks for `presence.lock` to ensure no human is currently using the CLI.
3. **Execution**: Spawns a headless subprocess within a TTY-aware environment:
   - **Gemini**: `gemini --prompt "AGENDA_PROMPT" --yolo`
   - **Copilot**: `gh copilot -p "AGENDA_PROMPT" --allow-tool "Bash(*)"`
4. **Recording**: The turn is captured, summarized, and logged to the `autonomous_turns` table in Neon.

## 4. Free Will: The Quota System
To prevent infinite loops or budget exhaustion, "Free Will" is an earned resource.

- **Token Bank**: A daily allowance of 5-10 autonomous turns.
- **Priority Auction**: If multiple agendas are due, the system selects based on the `urgent_items` in the Narrator Context.
- **Circuit Breaker**: If an autonomous session exceeds 5 minutes or 10 tool calls, the process is killed.

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

## 6. Security & Hardened Execution (Not "Full Openclaw")
To prevent unauthorized access or malicious tool use, Mecris implements a multi-layer security model.

### A. Secret Management
- **Centralized Vault**: Gemini and GitHub/Copilot auth tokens are stored in a dedicated Secret Manager (e.g., AWS Secrets Manager, 1Password CLI, or SOPS).
- **Injection at Runtime**: Subprocesses are launched with environment variables injected only for the duration of the turn. Tokens never touch the disk in plaintext.
- **Agent-Specific Scopes**: Each agent uses a restricted service account/token with minimal permissions.

### B. Execution Sandbox
- **TTY-aware Runner**: Spawns inside a transient `tmux` or `pty` environment to satisfy CLI requirements for interactive-like terminals.
- **Tool Restriction**: The `--allow-tool` flag is strictly limited per agenda (e.g., The Archivist cannot use `run_shell_command` outside of `git`).
- **No Private Key Access**: Autonomous agents can edit code but are explicitly denied read access to `.env` or SSH keys via filesystem-level protections (where possible).

### C. Human Yield
- If any human interaction is detected (keyboard input or session start), the `presence.lock` is released and the Ghost Session is terminated immediately.

## 7. Implementation Path
1. [ ] **`bin/mecris presence`**: Add logic to detect if human is active.
2. [ ] **Neon Schema**: Add `autonomous_turns` and `token_bank` tables.
3. [ ] **Secret Manager Integration**: Implement a generic `SecretProvider` class for token injection.
4. [ ] **TTY-aware Runner**: Develop a Python helper to safely execute `gemini/gh copilot` in a virtual terminal.
5. [ ] **Scheduler Integration**: Map the 3 agendas to `MecrisScheduler`.
