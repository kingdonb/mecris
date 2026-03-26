# 🗺️ MECRIS ROADMAP 2025

> **Mission**: Transform Mecris from reactive MCP server to autonomous cognitive agent with rich contextual awareness

## 📊 Current Status
- **Budget**: $23.19 remaining (43 days @ $30/month ceiling)
- **Foundation**: Production-ready MCP server with Beeminder, Budget, and Twilio integrations ✅
- **Gap**: No autonomous wake-up/nagging capability — *this is the core missing piece*

---

## 🎯 Four Core Goals

### **GOAL 0: Alpha Hardening & SLSA Security (Target: v0.1.0)** 🛡️
**Priority**: CRITICAL | **Timeline**: 1-2 weeks | **Budget Impact**: $0

**Current Problem**: Mecris is transitioning from a single-user local prototype to a multi-tenant ecosystem. We need synchronized versioning across Android, Spin, and Python, alongside strict security controls, before letting additional users on board.

**Solution**: The "Alpha Hardening" phase focuses on securing data isolation and creating a reproducible, SLSA-compliant build pipeline.

**Deliverables**:
- [ ] **SLSA Build Level 1**: Automated GitHub Actions CI pipeline for Android APK, Spin Wasm, and Python packages, featuring `actions/attest-build-provenance` to generate `.intoto.jsonl` files.
- [ ] **Strict Multi-Tenancy**: Audit all SQL queries to ensure `user_id` bounds. Ensure integrations (like Clozemaster) use *per-user* encrypted credentials stored in the DB, rather than global environment variables.
- [ ] **Mandatory Encryption**: Remove all plaintext token fallbacks in the Rust and Python backends. The system must fail fast if `MASTER_ENCRYPTION_KEY` is not present.
- [ ] **The Wipe Test**: Validate the end-to-end bootstrap flow for a completely fresh user.

### **⚠️ Forward-Looking Statements: Path to v1.0.0 (Subject to Change)**
*The following defines the long-term convergence of our security posture (SLSA) and feature development (Autonomy & RAG).*

**Target v0.3.0 (Beta): The Autonomous Shift**
*   **Feature Focus:** The Proactive "Wake-Up" Engine (Goal 1). Mecris begins running as a background daemon, using heuristics to send unprompted SMS/WhatsApp notifications when walking goals are at risk.
*   **Security Focus:** **SLSA Build Level 2 (Hosted & Authenticated)**. We upgrade the CI pipeline to use short-lived OIDC tokens and Sigstore. This cryptographically proves that the build artifacts originated from our GitHub Actions runners and were not forged on a developer's local machine.

**Target v0.5.0 (Release Candidate): Contextual Awareness**
*   **Feature Focus:** Knowledge Base & RAG Integration (Goal 2). Mecris can now converse with your Obsidian vault and `/docs`. The Android app interface expands beyond a dashboard into a conversational AI client.
*   **Security Focus:** **SLSA Build Level 3 (Hardened)**. Transition to isolated, ephemeral build environments using officially vetted builders (e.g., `slsa-github-generator`). This ensures the build process itself cannot be tampered with to inject malicious code into the artifacts or the `.intoto.jsonl` provenance files.

**Target v1.0.0 (General Availability): The Hermetic System**
*   **Feature Focus:** Complete contextual integration (Goal 3) and multi-user polish. Settings pages allow any user to bring their own API keys (encrypted on-device) to leverage the Mecris engine.
*   **Security Focus:** **SLSA Build Level 4 (Hermetic & Reproducible)**. The highest level of software supply chain security. 
    *   *Two-Person Reviews:* Enforced branch protection requiring multiple approvals for code changes.
    *   *Hermeticity:* Builds run entirely offline. All Rust crates and Android Gradle dependencies are pre-fetched, hashed, and vendored. 
    *   *Reproducibility:* Compiling the source code twice guarantees a byte-for-byte identical binary, proving absolute build integrity before any App Store submission.

---

### **GOAL 1: Autonomous Deployment & Nagging System** 🚨
**Priority**: HIGHEST | **Timeline**: 2-3 weeks | **Budget Impact**: ~$2-3

**Current Problem**: You're "doing very poorly" at daily walks despite having all the tracking infrastructure in place. Mecris has Twilio, it knows your goals, but it doesn't autonomously wake up to check on you.

**The Ground Truth**: We will develop the **Mecris CLI (`mecris` command)** to serve as the authoritative interface for both humans and agents. This CLI will underpin the autonomous system, providing explicit handles for all system operations.

**Agent Agenda**: Implement the **Autonomous Continuum** design (`docs/AGENT_AGENDA_DESIGN.md`) enabling headless "Ghost Sessions" via Gemini and Copilot CLIs.

**Solution**: Deploy autonomous scheduler that:
- Runs periodic health checks (cron-based or containerized scheduler)
- Evaluates narrator context using heuristic functions
- Spawns autonomous agents (Archivist, Auditor, Narrator) using a TTY-aware loopback.
- Uses the `mecris` CLI handles for all internal state transitions and "private entrypoints".

**Deliverables**:
- [ ] **The `mecris` CLI**: A Python-based CLI entry point with subcommands for `budget`, `goals`, `sync`, and `internal`.
- [ ] **Headless Loopback**: Subprocess wrapper for `gemini --yolo` and `gh copilot`.
- [ ] **Secret Manager Integration**: Hardened token injection for autonomous turns.
- [ ] Heuristic decision engine for notification triggers
- [ ] Smart nagging algorithms (time-of-day, goal urgency, success patterns)
- [ ] Web dashboard for check-in status (optional, lightweight)

**Infrastructure**: Build on existing FastAPI server + Twilio integration

---

### **GOAL 2: Knowledge Base & RAG Integration** 📚
**Priority**: HIGH | **Timeline**: 4-6 weeks | **Budget Impact**: ~$3-5

**Vision**: Transform Mecris documentation and personal context into a conversational knowledge base using Obelisk framework.

**Approach**: Don't reinvent the wheel — use Obelisk's proven Obsidian→Docs→RAG pipeline.

**Solution Components**:
- Convert existing `/docs` and personal Obsidian vault to structured knowledge base
- Separate public docs (publishable) from private context (work notes, personal details, PII)
- Implement "conversation with your docs" capability integrated with current Claude Code experience
- Local inference preferred (privacy + cost) with cloud fallback for complex queries

**Deliverables**:
- [ ] Mecris documentation structured for Obelisk processing
- [ ] Private context integration (work notes, personal data) with PII protection
- [ ] RAG query interface integrated with narrator context
- [ ] Local model deployment pipeline (budget-conscious)

**Budget Strategy**: Prioritize open-source/local solutions, cloud APIs only for complex reasoning

---

### **GOAL 3: Chrome Bookmarks Context Integration** 🔖
**Priority**: MEDIUM | **Timeline**: 3-4 weeks | **Budget Impact**: ~$1-2

**Vision**: Your browsing history becomes part of Mecris's contextual awareness — find that thing you bookmarked based on vague descriptions.

**Technical Approach**:
- Direct JSON file reading from `~/Library/Application Support/Google/Chrome/Default/Bookmarks`
- Chronological organization analysis (leverage your existing bookmark organization patterns)
- Semantic search over bookmark titles/URLs + optional content indexing for key bookmarks
- Integration with narrator context for reading pattern insights

**Deliverables**:
- [ ] Chrome bookmarks JSON parser and MCP endpoint integration
- [ ] Semantic search capability for "find that thing I bookmarked"
- [ ] Reading pattern analysis for narrator context insights
- [ ] Optional: content indexing for high-value bookmarked pages

**Cost Efficiency**: Local processing + lightweight embedding models

---

### **GOAL 4: AI Coding Framework Formalization** 🛠️
**Priority**: MEDIUM | **Timeline**: 2-3 weeks | **Budget Impact**: ~$0-1

**Current State**: Using Claude Code successfully, but no formal evaluation of alternatives.

**Goal**: Make informed decision about long-term development approach — stick with Claude Code or adopt agent framework.

**Evaluation Targets**:
- Current: Claude Code (known working solution)
- Alternatives: Aider, Cursor, Open Interpreter, AutoGPT-style frameworks
- Criteria: Cost efficiency, code quality, integration with Mecris architecture

**Deliverables**:
- [ ] Formal evaluation framework for AI coding tools
- [ ] Proof-of-concept implementations using 2-3 alternative frameworks
- [ ] Cost-benefit analysis aligned with <$30/month constraint
- [ ] Decision document and implementation plan for chosen approach

**Philosophy**: "If there's an established framework that does better what we already do, let's use it"

---

## 📅 Implementation Timeline

**Weeks 1-2: Phase 0 - Alpha Hardening** (CRITICAL PATH TO v0.1.0)
- Audit SQL queries for multi-tenant data boundaries.
- Strip all plaintext token logic and enforce strict `MASTER_ENCRYPTION_KEY` presence.
- Refactor Clozemaster credentials from global env vars to encrypted per-user DB rows.
- Set up GitHub Actions CI for SLSA Build Level 1 (Automated builds & `.intoto.jsonl` provenance).

**Weeks 3-5: Autonomous Deployment** (Goal 1)
- Week 1: Design autonomous scheduler architecture
- Week 2: Implement core nagging system with Twilio integration  
- Week 3: Deploy, test, and refine heuristic decision making

**Weeks 2-4: AI Framework Evaluation** (PARALLEL)
- Week 2: Survey and shortlist alternatives to Claude Code
- Week 3: Build proof-of-concepts with top 2-3 candidates
- Week 4: Make decision and document transition plan if needed

**Weeks 4-8: Knowledge Base Integration**
- Weeks 4-5: Obelisk integration and docs structuring
- Weeks 6-7: RAG implementation with local inference priority
- Week 8: Integration testing and private context security validation

**Weeks 6-10: Chrome Integration**
- Weeks 6-7: Chrome bookmarks parser and basic search
- Weeks 8-9: Semantic search and narrator context integration
- Week 10: Reading pattern analysis and insights

## 💰 Budget Projection

| Goal | Estimated Cost | Justification |
|------|---------------|---------------|
| Autonomous Deployment | $2-3 | Minimal cloud resources, mostly cron/local scheduling |
| Knowledge Base/RAG | $3-5 | Local inference setup, occasional cloud API usage for complex queries |
| Chrome Integration | $1-2 | Local processing, lightweight embeddings |
| Framework Evaluation | $0-1 | Research phase, minimal API costs for testing |
| **TOTAL** | **$6-11** | Well within 43-day budget of $23.19 |

**Risk Mitigation**: Start with local/free solutions, add cloud capabilities only when proven necessary.

## 🎖️ Success Metrics

**Goal 1 Success**: You actually get nagged about walks and respond to the nagging
**Goal 2 Success**: You can ask Mecris "what did I decide about X?" and get accurate answers from your docs
**Goal 3 Success**: You can ask "find that article about Y" and Mecris locates it from your bookmarks  
**Goal 4 Success**: Development velocity increases measurably with chosen framework

## 🚧 Future Considerations

- **Secure SSE Mode**: Re-enable the FastAPI/SSE server once hardened with OIDC authentication for secure remote access.
- **AWS Account Terraform Module**: Mentioned but deferred — security-first cloud infrastructure for eventual scaling
- **Multi-user Support**: Architected for single-user but considering friend/neighbor sharing
- **Advanced Scheduling**: Beyond daily nagging — project deadline management, goal sprint planning

---

**Next Action**: Begin Goal 1 implementation — the autonomous nagging system that will finally get you walking daily. 🚶‍♂️