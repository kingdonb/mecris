# AI Framework Evaluation

> **Mecris Strategic Document**
> *Formal evaluation of AI coding frameworks against the Claude Code baseline. Budget constraint: <$30/month. Objective: maximize development velocity for Mecris architecture work (Goal 4).*

## 📊 Evaluation Matrix

Scoring: 1 (poor) → 5 (excellent). Weights reflect Mecris priorities.

| Dimension | Weight | Claude Code | Aider | Open Interpreter | Notes |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Cost** | 30% | 3 | 4 | 4 | Claude Code on Sonnet 4.6 ~$15-25/session-month; Aider can use cheaper models or local LLMs |
| **Speed (iteration)** | 20% | 4 | 4 | 3 | Claude Code and Aider both offer tight edit-test loops; Open Interpreter has higher overhead |
| **Context Management** | 25% | 5 | 3 | 2 | Claude Code manages CLAUDE.md + memory files; Aider uses repo-map but no persistent strategy layer |
| **Autonomy / Agentic** | 25% | 5 | 2 | 3 | Claude Code can plan, execute multi-step tasks, and self-archive; Aider is single-shot per invocation |
| **Weighted Score** | — | **4.30** | **3.20** | **3.00** | |

### Dimension Definitions

- **Cost**: Total API spend per productive session-month at our workload level.
- **Speed (iteration)**: Time from task statement to committed, tested code change.
- **Context Management**: Ability to carry persistent project knowledge (CLAUDE.md, memory, session logs) across invocations and build a coherent mental model of the codebase.
- **Autonomy / Agentic**: Ability to plan, branch on failures, run tests, open GitHub issues, and archive state without human intervention.

---

## 🧪 Baseline: Claude Code (Current)

*Data as of 2026-04-25. Source: `session_log.md`, Neon `autonomous_turns` table.*

| Metric | Value |
| :--- | :--- |
| Sessions evaluated | ~47 (mecris-bot sessions) |
| Avg Android tests per session | 63 (0 failures baseline) |
| Python test baseline | 16 passed (presence scheduler) |
| PAT/workflow blockers this month | 1 (expired GITHUB_CLASSIC_PAT) |
| Features delivered (April 2026) | MomentumOrb, REMAINING TODAY, Behavioral Nudge, Spin SDK v4, Flow Fill Bar, Debt Coverage |
| Estimated session cost | Sonnet 4.6 — tracked in `token_bank` / `autonomous_turns` |

**Strengths**: Rich persistent context (CLAUDE.md + memory), multi-step autonomous execution, full GitHub MCP integration, native test-and-commit loop, TDG discipline enforced by skill layer.

**Weaknesses**: Paid per-token at Sonnet 4.6 rates; no local/free-tier fallback; context window compression can lose fine-grained history mid-session.

---

## 🔬 Aider Analysis

*Source: public benchmarks, SWE-bench leaderboard, project docs.*

**Billing model**: Passes through to whatever LLM is configured (GPT-4o, claude-sonnet, or a local Ollama instance). Can use free-tier or local models.

**Best fit for Mecris**: Single-file targeted edits where the repo-map gives sufficient context (e.g., refactoring a single Kotlin class or fixing a Python function). Not suited for cross-cutting changes that require project-wide context or autonomous multi-step planning.

**Gap**: Aider has no equivalent of the mecris-orient → mecris-plan → mecris-archive loop. Each invocation is stateless from Aider's perspective — session continuity must be managed by the human operator.

### Candidate use case: cost-sensitive targeted edits

If a session task is narrowly scoped (single file, clear spec), Aider + a cheap local model (e.g., Qwen3-8B via Ollama) could complete it for $0. The POC script below measures this hypothesis.

---

## 🔬 Open Interpreter Analysis

*Source: project docs, GitHub README.*

**Billing model**: Same pass-through model as Aider; can use local LLMs.

**Best fit for Mecris**: Data exploration, one-off analysis scripts, or tasks that naturally involve running shell commands in a REPL. Less suited to codebase-wide feature development.

**Gap**: Context management is session-scoped only. No repo awareness at the level of Aider's repo-map or Claude Code's CLAUDE.md.

---

## 📝 Recommendations

1. **Keep Claude Code as primary** for autonomous bot sessions. The mecris-bot workflow depends on MCP tools, GitHub API, multi-step planning, and session memory — none of which Aider or Open Interpreter provide.

2. **Pilot Aider for bounded human sessions** when the task is a single-file fix and budget is tight. Run `scripts/evaluate_aider.py --mode refactor` to establish a cost/quality baseline.

3. **Revisit after local LLM benchmarks**: `benchmark_helix.py` already probes Qwen3-8B. When `experiments/helix_benchmark/results.jsonl` has ≥10 runs, compare output quality against GPT-4o-mini as the Aider backend. If quality holds, the cost argument for Aider strengthens significantly.

4. **Do NOT switch the bot workflow to Aider**: The autonomy gap (score 2 vs 5) is fundamental, not incidental. Aider is a pair-programming tool, not an autonomous agent.

---

## 📅 Evidence Log

| Date | Event | Outcome | Source |
| :--- | :--- | :--- | :--- |
| 2026-04-25 | Initial matrix created | Claude Code scores 4.30/5 weighted | This document, kingdonb/mecris#205 |
| 2026-04-25 | POC script created | `scripts/evaluate_aider.py` committed | yebyen/mecris#277 |

*Run `scripts/evaluate_aider.py` and append results here after each evaluation run.*
