# Feature Specification: Autonomous Presence & Sync Architecture (v1.0)
**Status:** DRAFT (Reverse-Engineered from User Interviews & Codebase)
**Date:** 2026-04-05
**Feature ID:** SYS-001 (Ghost Archivist & Ecosystem Synchronization)

## 1. System Ecosystem & Modalities (The "Fleet")
The Mecris system is distributed across several specialized modalities. To understand the "Ghost Archivist" and the sync logic, we must specify the fleet it operates within and its relationship to the "Useless Architecture" pattern.

### 1.1 The Modalities
*   **The Local MCP Server (Python)**: **The Vanguard.** This is the primary development environment and terminal interface. Business logic is developed, tested, and iterated here first. It manages local cron/scheduler tasks, reads goals, and provides proactive encouragement via the LLM.
*   **The WASM Brain (Fermyon Spin / Rust & Python)**: **The Consolidated Logic Core.** The eventual destination for business logic. Following the "Useless Architecture" pattern, the goal is *not* to rewrite everything in Rust. Instead, the vision is to use tools like `componentize-py` to compile our existing, proven Python logic directly into WASM components. This allows us to keep developing rapidly in Python (our successful vanguard) while deploying a language-agnostic binary that can be shared across the fleet (preventing the "three jobs instead of two" problem).
    *   *`sync-service`*: The main HTTP gateway. Ingests walk telemetry, decodes Pocket ID JWTs for security, and handles autonomous cloud sync (scraping Clozemaster and updating Beeminder) if the local Python server goes offline.
    *   *`review-pump` & `arabic-skip-counter`*: Existing logic modules. Ultimately, these should be generated directly from our Python codebase rather than maintained as separate Rust projects.
*   **The Android App (Client)**: A **Purpose-Built Telemetry Bridge**. This component solves a very specific, difficult problem: accessing raw device telemetry (Health Connect step counts) which is heavily gated by mobile OS permissions engines. 
    *   *Capabilities:* It is surprisingly complex, featuring robust identity management (OIDC/Pocket ID login), a dedicated settings page for sync configuration, and the necessary native Android permission flows to read Health Connect data.
    *   *Role:* It is the "only possible solution" for reliable, passive step tracking without relying on closed proprietary APIs (like Google Fit's deprecated cloud endpoints). It securely transmits this data back to the WASM Brain.
*   **The GitHub Actions Bot (`mecris-bot` / Claude Code)**: **The Autonomous Executor.** 
    *   *Implementation:* An Ubuntu runner executing the `@anthropic-ai/claude-code` CLI via a GitHub Actions cron schedule. It runs roughly every 2 hours from 8:00 AM to 8:00 PM, plus once at midnight (US/Eastern time).
    *   *The Gall Loop:* Operates on a strict, 4-step execution loop modeled on Urbit's Gall agent pattern:
        1. `/mecris-orient` (`on-peek`): Reads the current system state, `NEXT_SESSION.md`, and active goals to determine the highest priority task.
        2. `/mecris-plan` (`on-poke`): Opens a GitHub Issue defining the specification and intent *before* touching code.
        3. *Execution*: Modifies code using `Skill(tdg:atomic)` to ensure test-driven, atomic commits. It stops strictly at 65 turns.
        4. `/mecris-archive` (`on-save`): Closes the issue, updates documentation, and prepares for the next run.
    *   *Resilience:* The workflow handles `git push` autonomously. If it encounters a rebase conflict, it triggers a constrained "Rescue Session" where the bot is revived specifically to incorporate upstream code, resolve conflicts using `mecris-rebase`, and ensure the session's work is not lost.
*   **The "Side Brain" Reviewer (Gemini)**: The user interacts with Gemini via the local terminal to review Claude's nightly commits, acting as a skeptical supervisor before deployment.

### 1.2 Architectural Philosophy & The Hierarchy of Truth
Mecris shares DNA with the `yebyen/useless` reference architecture (which uses a Kubernetes runtime controller and a database-less design leveraging the K8s API). We do not adopt Useless entirely, but we observe and preserve the parallels.

**The Hierarchy of Truth:**
1.  **The "City-on-a-Hill" Vision**: The ultimate, perfect conceptual design of the system.
2.  **The Specification (SDD)**: The closest written approximation of the vision. This document is the canonical reference.
3.  **The Codebase (Python/Rust/WASM)**: The current, pragmatic reality. It is *not* the source of truth; it is often loaded with defects. However, on a day-to-day basis, it does the job we hired it for. We preserve existing behavior except where a formal defect (like DEFECT-003) is identified. 

**Logic Consistency**: Before logic is vacuumed into the Spin WASM application, the specification must be flushed out. We continue development in Python because it is our vanguard, not because it is infallible. 

### 1.3 Modality Capability Matrix (Adoption Guide)
For developers adopting this framework, this matrix serves as a decision guide. 

*Crucially: 99% of framework adopters will not need the Android app.* The framework lets you pick the combination of codebases that solve your problems. By omitting components, you save maintenance overhead (avoiding "three jobs instead of two") but lose specific capabilities.

| Component / Modality | Primary Role | Capabilities Gained | Capabilities Lost if Excluded |
| :--- | :--- | :--- | :--- |
| **Python MCP Server** | Vanguard Dev & Strategic Synthesizer | Proactive terminal guidance, rapid logic iteration, local scheduling. Crucially: Unifies disparate data streams (weather, health, budget, goals) into a cohesive context for LLM analysis. | Lose the ability to generate high-level strategic insights across complex data intersections. |
| **Spin WASM Brain** | Logic Consolidation & Cloud | High-availability cloud backend, language-agnostic logic sharing (`componentize-py`). | If excluded, you rely *strictly* on local machine uptime (MCP) for autonomous tasks. |
| **Android App** | Telemetry Collection & Cloud Trigger | Raw hardware data (Health Connect steps), robust OIDC login, mobile background worker. | Lose passive step tracking. Lose the ability to trigger the Spin Cloud backend autonomously (since Spin lacks its own OIDC identity currently). |
| **Pure "Skynet" (Spin + Cron)** | Ultimate Autonomy | If there is no gap to the required data (e.g., no Health Connect wall), Spin + an external Cron achieves full autonomy with zero MCP, LLM, or Android involvement. | Requires all data sources to have open, cloud-accessible APIs. |

### 1.4 The Roots of Mecris (Why the MCP Exists)
While the pure "Skynet" model offers perfect autonomy, it lacks intelligence. The Python MCP server was built to solve two foundational problems that require synthesis, not just automation:
1.  **Budget Stewardship**: The first goal was "avoid spending all of our tokens in one place." The MCP unifies financial data (Groq, Anthropic) to guide the LLM in spending its token budget wisely across the fleet.
2.  **Contextual Motivation**: The second goal was to fix the human element of the Beeminder `bike` goal (getting outside daily). By feeding an LLM the user's step count alongside the current weather and goal buffer, the LLM transcends simple data logging and provides *strategic insight and motivation*. A basic cron job logs data; the MCP + LLM combination drives human behavior.

## 2. Daily User Flow (The Target Experience)
1.  **The Morning Briefing**: The user opens the terminal. Gemini fetches active goals and delivers personalized encouragement.
2.  **The Autonomous Audit**: The user instructs Gemini to review the commits generated by Mecris-bot (Claude) overnight. Gemini acts as a skeptical "side brain," reviewing code and preparing for manual `0.0.1-alpha.X` tag deployments.
3.  **The Background Pulse**: The Android app (when active) and local MCP server sync telemetry to Neon DB and Beeminder.
4.  **The Ghost Archivist (Reality Enforcement)**: An autonomous system periodically snapshots the day's true state (e.g., before and after midnight) to update internal records and opportunistically sync Beeminder.

## 3. The Ghost Archivist Specifications

### 3.1 Intent
The Ghost Archivist is explicitly **not** designed to prevent goal derailment. Prevention is the responsibility of the human user performing the measured activity. Beeminder handles notifications (Android, email). 
The Archivist's primary purpose is to **enforce reality**: it ensures the system's internal records (Neon DB) accurately reflect the user's progress or lack thereof. It runs continuously and independently of user presence, logging discrepancies, pushing actual data to Beeminder, and accepting that accurate derailments are a valid outcome of inactivity.

### 3.2 Heuristics & Triggers
*   **Continuous Reconciliation**: The Ghost operates "continuously" in the GitOps sense—it runs on a defined, scheduled interval (e.g., hourly cron, specifically ensuring coverage before and after midnight), **regardless** of whether the user's `presence` status is active or silent.
*   **Idempotent Execution**: It evaluates the current state against the recorded state and only performs API calls if a discrepancy exists.

### 3.3 Target Actions (The "Archival Turn")
When triggered, the Ghost must:
1.  **Reality Sync**: Pull truth from sources (like Clozemaster API) and update internal records (Neon DB).
2.  **Beeminder Opportunistic Update**: If the reality sync reveals new data, push it to Beeminder.
3.  **Log Inactivity**: If no work was done, explicitly log that no work was done.
4.  **Physical Activity Proxy**: *DEFECT NOTED (See Section 5).* Do NOT push artificial 0.0 data to odometer goals (like `bike`) to save the user. If the user didn't walk, they derail.

### 3.4 Constraints (The "No-LLM" Rule)
The Ghost Archivist is a purely deterministic, conventional background process. It "reads dials and writes to spreadsheets."
*   **No Inferencing**: The Ghost explicitly does **not** have access to an LLM and does not consume AI tokens. It is entirely distinct from the `mecris-bot` (which runs ~8 times a day and *does* use an LLM for complex tasks). The Ghost's scope is strictly bounded to programmatic data synchronization and reality enforcement.

## 4. Success Criteria
*   **SC-001 (Reality Enforcement)**: The Ghost Archivist runs continuously (interval-based) and successfully updates internal logs and Beeminder *only* when a discrepancy exists between recorded state and actual reality. It never pushes 0.0 "fake" data to odometer goals.
*   **SC-002 (Bot Workflow Reliability)**: The `mecris-bot` GitHub Action demonstrates a >90% success rate in completing its full Gall loop (`/mecris-orient` -> `/mecris-plan` -> `tdg:atomic` -> `/mecris-archive`).
*   **SC-003 (Conflict Rescue)**: When the bot encounters a rebase conflict on `git push`, the automated Rescue Session is triggered and successfully resolves the conflict via `mecris-rebase` without human intervention.
*   **SC-004 (Logic Consolidation Tracking)**: Progress is actively tracked toward moving Python business logic into the WASM Brain via `componentize-py`. Success is measured by a reduction in duplicated code across languages and the removal of bespoke Rust logic modules.
*   **SC-005 (Cloud Fallback Autonomy)**: If the local Python MCP goes offline, the Spin WASM deployment (acting as the cloud Ghost Archivist) successfully assumes responsibility for reading APIs and updating Neon/Beeminder.

## 5. User Stories

### General Ecosystem Usage
*   **US-001 (Morning Encouragement)**: As a user, when I start my terminal, I want context-aware encouragement based on my current goals.
*   **US-002 (Bot Supervision)**: As a user, I need Gemini to review Claude's nightly commits to act as a skeptical human-in-the-loop and prevent regressions.
*   **US-003 (Python Vanguard)**: As a developer, I want to write and iterate on all business logic in Python first, ensuring it is fully specified and consistent before it is compiled or ported to the WASM brain.

### Autonomous Bot (`mecris-bot`) Operations
*   **US-004 (Contextual Orientation)**: As the autonomous bot, I must begin every run by calling `/mecris-orient` to read the system state and `NEXT_SESSION.md` so that I never invent phantom work and always execute the highest-priority task.
*   **US-005 (Spec-Driven Planning)**: As the autonomous bot, I must use `/mecris-plan` to open a formal GitHub Issue documenting my intent *before* writing code, so the user can audit my thought process even if execution fails.
*   **US-006 (Atomic Execution)**: As the autonomous bot, I must use the Test-Driven Generation (`tdg:atomic`) skill to produce small, verified, and atomic commits, preventing massive, unreviewable diffs.
*   **US-007 (Graceful Archiving)**: As the autonomous bot, when I reach my turn limit or complete a task, I must call `/mecris-archive` to summarize my work in `SESSION_LOG.md` and close the GitHub Issue, ensuring the state is serialized for the next run.
*   **US-008 (Conflict Rescue)**: As the autonomous bot, if my GitHub Action fails to push due to a rebase conflict, I want to be re-triggered in a constrained "Rescue Session" solely to resolve the conflict via git CLI tools, preserving my work without requiring human intervention.

### WASM Brain & Logic Consolidation
*   **US-009 (Deterministic Sync)**: As a system architect, I want the Spin WASM brain to contain the exact calculation logic for modules like the `review-pump` and `arabic-skip-counter` so the Android app and Python MCP server simply consume the output without needing complex localized logic.
*   **US-010 (Cloud Fallback Autonomy)**: As a user, when my local Python server's heartbeat goes stale in the Neon DB, I want the Spin `sync-service` endpoint to safely assume responsibility for pulling Clozemaster data and updating Beeminder.
*   **US-011 (JWT Security Boundary)**: As a security baseline, the Spin WASM deployment must natively decode and enforce Pocket ID JWTs to ensure cloud endpoints are protected from unauthenticated access.

### Ghost Archivist Operations
*   **US-012 (Reality Enforcement)**: As a user, I want the Ghost Archivist to run continuously (before and after midnight) to ensure my internal databases exactly match reality, even if that reality means I derail on a goal.
*   **US-013 (The "Dead Battery" Scenario)**: As a user, if my local devices are offline, I want the cloud WASM deployment to autonomously record my actual progress or failure so my logs are perfectly accurate.
*   **US-014 (Odometer Clarity)**: As a user, I do not want to see artificial "0.0" entries in my step/distance logs. I own my derailments.
*   **US-015 (Modality Selection)**: As a framework adopter, I want to understand exactly what capabilities I gain or lose if I choose not to build an Android app or a Spin WASM module for my own deployment.

## 6. Known Defects & Architectural Gaps

### 6.1 DEFECT-001: The Cloud Fallback Failure (Critical)
*   **Description**: The local Python cron jobs fail if the laptop is asleep. The intended cloud reality-enforcer (Spin WASM deployment) lacks access to the user's OIDC context and/or the `MASTER_ENCRYPTION_KEY` required to decrypt Beeminder tokens.
*   **Impact**: US-013 cannot be satisfied. If local machines are offline, reality is not recorded at the day boundary.
*   **Proposed Resolution**: The Spin deployment must be granted securely scoped access to the master key, or a dedicated "Service Account" OIDC profile must be created.

### 6.2 DEFECT-002: CI/CD Deployment Bottleneck
*   **Description**: Because artifacts are unversioned and bots cannot safely push and await CI validation, deployments are blocked until manually orchestrated via Gemini.
*   **Impact**: US-002 requires manual daily intervention.

### 6.3 DEFECT-003: Odometer Ghost Heartbeats (Derailment Prevention Bias)
*   **Description**: The current Python implementation incorrectly pushes a 0.0 value to the `bike` goal if no activity is found, attempting to "save" the user.
*   **Impact**: Violates US-004 and US-006. The system should not forge data to prevent derailments.
*   **Resolution**: Remove the 0.0 push logic and allow Beeminder's native mechanisms (or derailments) to handle inactivity.