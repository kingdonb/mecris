# 🚀 ACTIVE_BACKLOG.md: The Trunk

This document is the high-fidelity source of truth for the current development cycle. It combines the most critical items from the legacy TODOs and Roadmaps.

## 1. Goal 1: The Autonomous Nagging System (CRITICAL)
*Objective: Ensure daily accountability occurs without user prompting.*

- [ ] **Nag Ladder Refinement**:
  - Integrate `Review Pump` velocity (from `services/review_pump.py`) into the Twilio SMS content.
  - Implement a "Damping" check: Ensure no more than 1 SMS per 4-hour window, even if the user is failing multiple goals.
- [ ] **Ghost Archivist Heartbeat**:
  - Configure the `scheduler.py` to run a "Strategic Review" turn once every 24 hours.
  - The turn should produce a `MORNING_BRIEFING.md` in the user's Obsidian vault (via `obsidian_client.py`).
- [ ] **Secret Manager Hardening**:
  - Transition the `mecris-bot` workflow to use the `Secret Manager` integration for all Neon/Beeminder/Twilio tokens instead of raw environment secrets where possible.

## 2. Goal 2: Knowledge Base & RAG Integration (HIGH)
*Objective: Give Mecris long-term memory of project decisions and personal history.*

- [ ] **RAG Productionization**:
  - Automate the indexing of `SESSION_LOG_*.md` files into the vector store.
  - Implement a `Skill(ask-mecris)` that uses `rag_retriever.py` to answer architectural questions before the agent starts work.
- [ ] **Obsidian Narrative Thread**:
  - Extract "Commitments" (items tagged with `#commitment` or `#goal`) from the last 7 days of Daily Notes.
  - Automatically update the relevant Beeminder goal if a commitment is marked as completed in Obsidian.

## 3. Infrastructure & Maintenance (ONGOING)
- [ ] **SLSA Build Level 3**: Finalize the build provenance for the Android APK and Spin Wasm components.
- [ ] **PII Encryption Audit**: Ensure that the recent multi-tenancy migrations haven't left any plaintext PII (phone numbers) in the Neon logs.
- [ ] **Budget Governor Tuning**: Adjust the edge-interceptor limits to allow the Ghost Archivist to run even if the user's monthly budget is < 5% remaining (a "reserve" budget for basic nagging).

## 4. Completed recently ✅
- [x] Full migration from SQLite to Neon (Postgres).
- [x] Context Burn mitigation in `TDG.md` (-q --tb=short).
- [x] Restoration of `mecris-bot` GitHub Actions workflow.
- [x] Formalization of Architectural Evolution research project.

## Infrastructure and DX
- [ ] Add --help command support to mcp_server.py to allow better skill discovery for autonomous agents.
