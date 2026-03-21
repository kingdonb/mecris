# 🛡️ Mecris Security-First Roadmap

> **Mission**: Establish a zero-trust foundation and secure PII before scaling to multi-tenancy.

---

## 🏛️ Phase 1: Security Foundations (Steps 1-10)

1.  **JWT Signature Verification (High Priority)**
    - Replace the insecure `extract_user_id` in `sync-service/src/lib.rs` with a robust `verify_jwt` function.
    - Implement fetching and caching OIDC public keys (JWKS) via `spin_sdk`.
    - Validate `iss` (issuer), `aud` (audience), and `exp` (expiration) claims.
    - **Step 1 Goal**: Reject any JWT not cryptographically signed by the trusted Pocket ID provider.

2.  **OIDC Configuration Management**
    - Move OIDC discovery URL to a Spin environment variable.
    - Implement a "bootstrap" admin user identified by a specific `sub`.
    - **Step 2 Goal**: Centralize trust configuration in Fermyon Cloud secrets.

3.  **PII Encryption at Rest & Third-Party OAuth Transition**
    - Integrate AES-256-GCM encryption in the Rust backend for `beeminder_token_encrypted`.
    - **Transition to Beeminder Client OAuth**: Avoid storing Beeminder tokens entirely by implementing the [Beeminder Client OAuth flow](https://api.beeminder.com/#client-oauth).
    - **Clozemaster Auth Research**: Investigate if Clozemaster's Google/Apple OAuth flow can be leveraged for the scraper to avoid password storage. Derive their private API directly from the React model to minimize data scraping overhead.
    - Store any remaining sensitive secrets (e.g., encryption keys) in a hardware-backed secret store.
    - **Step 3 Goal**: Eliminate token/password storage where possible; encrypt what remains.

4.  **PKCE and Nonce Audit**
    - Audit the Android AppAuth flow to ensure Proof Key for Code Exchange (PKCE) is strictly enforced.
    - Implement nonce verification to prevent replay attacks on the token exchange.

5.  **Rate Limiting & Abuse Prevention**
    - Implement a token-bucket rate limiter in the Spin backend to prevent brute-force probing of `/walks`.

6.  **Secure Admin "Break-Glass" Flow**
    - Design an internal "Admin" API path that requires a separate, long-lived master key for emergency recovery.

7.  **Key Rotation Strategy**
    - Implement logic to handle JWKS key rotation from the OIDC provider without system downtime.

8.  **Database Row-Level Security (RLS)**
    - Implement PostgreSQL RLS on the Neon DB to provide a secondary layer of isolation between user rows.

9.  **Audit Logging**
    - Create a tamper-evident audit log for security-critical events (e.g., failed auth, token updates).

10. **Step 10: End-to-End Encryption (E2EE) for Sensitive Metrics**
    - **Goal**: Transition to a model where the Spin backend only handles *encrypted* telemetry. The Android app encrypts detailed data with a user-derived key; the backend only processes the metadata needed for Beeminder sync.

---

## 👥 Phase 2: Architectural Multi-Tenancy (Steps 11-30)

11. **Strict Row-Level Isolation (Application Layer)**
    - Update all Python and Rust backend queries to include mandatory `WHERE user_id = :verified_sub`.

12. **User-Scoped Secrets API**
    - Add authenticated endpoints to allow users to update their own Beeminder and Clozemaster credentials.

13. **Stateless MCP Refactoring**
    - Refactor `mcp_server.py` to accept user-provided context or OIDC tokens for every tool call.

14. **Documenting History & Lore**
    - (Complete) Capture the evolution from SQLite to Spin/Neon in `docs/HISTORY_AND_LORE.md`.

---

## 🌐 Phase 3: Zero-Trust & Global Scale (Steps 31-50)

31. **Federated OIDC Support**
    - Allow users to "Bring Your Own OIDC" (Authentik, Google, etc.).

34. **Akamai/Edge Migration Plan**
    - Research Akamai serverless compatibility for long-term platform independence.

50. **Step 50: Stateless "Satellite" Deployments**
    - **Goal**: Standardize a "Mecris Satellite" (Spin app + MCP server) that any user can deploy to their own cloud account. The central Mecris hub acts only as an OIDC discovery service and a global "accountability peer-discovery" mesh, giving users 100% ownership of their data and infrastructure.

---

## 📅 Immediate Next Steps (Sprint A)

1.  **Code**: Implement `verify_jwt` in `mecris-go-spin/sync-service/src/lib.rs`.
2.  **Infrastructure**: Set up the JWKS caching mechanism using Spin KV.
3.  **Validation**: Test with a known-valid JWT from the current Pocket ID instance.
