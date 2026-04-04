# Security Remediation Strategy: Progressive Hardening
**Date:** April 4, 2026
**Strategic Goal:** Architect a system that enables frictionless mass adoption (Tier 1) while enforcing rigorous security for personal cloud deployments (Tier 2).

## 1. Balancing Security with "Mass Adoption" Vision
The [Security Audit (2026-04-04)](SECURITY_AUDIT_REPORT_2026_04_04.md) identified critical gaps in encryption, authorization, and identity assumption. However, strictly enforcing cloud-level security (JWTs, mandatory external DBs, complex key management) would destroy the onboarding experience for new users. 

To solve this, we are adopting a **Progressive Hardening** strategy. Mecris must be able to run seamlessly in a local, unauthenticated, zero-config state, while retaining the ability to seamlessly "harden" into a multi-tenant cloud application.

## 2. Maturity Tiers & Official Support Model
We explicitly categorize Mecris architectures into three support tiers. Documentation and features will clearly separate Core pathways from Experimental usage.

| Tier | Name | Description | Persistence | Auth / Identity | Encryption |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tier 1** | **Standalone Local (Core)** | The "North Star" for mass adoption. A user downloads the CLI and runs it locally. | Local SQLite (or `:memory:`). | None (Uses persistent local UUID). | **Optional** (Quiet Default + Warnings). |
| **Tier 2** | **Multi-Tenant / Hybrid (Advanced)** | Our current operating reality. Cloud backend, strict multi-user isolation. | Neon Postgres (Cloud). | JWT (Pocket ID) required. | **Mandatory.** Hard-fails if missing. |
| **Tier 3** | **Experimental (Community)** | Automation stubs, GitHub Actions, Cron-only scripts. | Ephemeral / File-based Cache. | Variable. | None required. |

## 3. The `MECRIS_MODE` Toggle & Identity Resolution
To resolve the `DEFAULT_USER_ID` vulnerability, we will introduce an explicit `MECRIS_MODE` configuration variable (`standalone`, `multi-tenant`, `hybrid`). 

**The "Shared Schema, Dynamic Context" Rule:**
Core logic (SQL queries) must *always* filter by `user_id`. The mode determines where that ID comes from:
- **`MECRIS_MODE=standalone`:** 
  - On first run, the CLI generates a persistent UUID (e.g., `local-abcd...`) and stores it in `~/.mecris/credentials.json`.
  - The MCP server reads this file and trusts it implicitly.
- **`MECRIS_MODE=multi-tenant`:** 
  - The MCP server acts as a **Stateless Resource Server**.
  - All FastAPI endpoints *must* require a valid `X-Mecris-Pocket-ID` JWT. 
  - The `user_id` is extracted strictly from the JWT `sub` claim. 
  - Unauthenticated requests receive `401 Unauthorized`.

## 4. Key Architectural Decisions

### A. SQLite Resurrection & Zero-Persistence
To support Tier 1, we will fully support SQLite using the exact same schema designed for Postgres. 
- For users who want absolutely no persistence, they can configure SQLite to use `:memory:`. 
- **Durable File-Based Caching:** To prevent API spamming (e.g., hitting Beeminder rate limits on every run in zero-persistence mode), we will implement a file-based `CacheProvider` (e.g., `~/.mecris/cache.json`) that operates independently of the database.

### B. Tier 3: GitHub Actions Support
We will *not* provide an official "Mecris Action." However, to prevent support burdens, we will document a `MECRIS_CACHE_DIR` environment variable. Documentation will provide a "hint" snippet showing how users can map this directory to `actions/cache@v4` to persist API state between ephemeral CI runs.

### C. Client-Side Token Management (The Login Flow)
For Tier 2, the MCP server will not handle complex OAuth flows. Instead, we will implement an "AWS CLI" style approach:
1. User runs `mecris login`.
2. CLI initiates an Authorization Code Flow with PKCE via a local loopback server (`http://localhost:random`).
3. Access and Refresh tokens are stored locally (`~/.mecris/credentials.json`).
4. **The CLI (not the server) is responsible for token lifecycle.** Before the CLI makes an internal request, it checks token expiry and uses the Refresh token if necessary.

### D. Local Leader Election
To coordinate background tasks (reminders) when a user runs both the CLI and a local server in `standalone` mode, we will bypass database locks and use a simple **File-Based Leader Lock** (e.g., `~/.mecris/scheduler.lock`).

### E. Mode-Driven Test Matrix
To ensure Tier 2 development doesn't break Tier 1, our CI pipeline will run the core test suite twice:
1. `MECRIS_MODE=standalone` using local SQLite.
2. `MECRIS_MODE=multi-tenant` using Neon Postgres and mocked JWT validation.

## 5. The Remediation Roadmap

### **Phase 1: Frictionless Hardening (Q2 2026)**
- **Quiet Default Encryption:** In `standalone` mode, if no `MASTER_ENCRYPTION_KEY` exists, log a prominent warning but allow plaintext storage of PII.
- **CLI Tooling:** Implement `mecris security enable-encryption` to generate a local key and seamlessly encrypt existing plaintext data.

### **Phase 2: Authorization Enforcement (Q2 2026)**
- Implement FastAPI middleware in `mcp_server.py` for `multi-tenant` mode that mandates JWTs.
- Remove all implicit `DEFAULT_USER_ID` fallbacks from data access logic.

### **Phase 3: The Data Portability Bridge (Q3 2026)**
- Implement `mecris migrate-to-cloud` as the ultimate mass-adoption exit ramp. This command will:
  1. Force encryption of all local plaintext PII.
  2. Sync local SQLite rows to the remote Neon database.
  3. Re-map the data from the persistent local UUID to the authenticated Pocket ID `sub`.

## 6. Conclusion
By explicitly separating Standalone ease-of-use from Multi-Tenant rigor, we can build a secure, cloud-ready application that remains highly accessible to new users. We provide the tools for users to secure their data when they are ready, without blocking them at the front door.
