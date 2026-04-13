# Data Architecture and Privacy Assessment

This document provides a thorough audit of the current state of data access, storage, and PII handling in the Mecris system. It is written to provide a clear technical understanding of how data moves through the system and the implications for user privacy.

## 1. Core Data Flow & Access Model

### The "Master Mode" Reality
The MCP (Model Context Protocol) server operates in what can be described as "Master Mode." While it honors multi-tenant identifiers (UUIDs) when provided, it possesses direct, unrestricted access to the Neon/Postgres database. 
- **Security Check Reality:** Authentication checks in the local MCP context are "permissive." The system relies on reading a UUID from a local file (`~/.mecris/credentials.json`) and using it to select rows in a database that the server operator controls. There is no cryptographic verification of the user's identity when the agent accesses the database through the MCP server.
- **Risk Flag:** Any individual or agent with execution rights on the host machine has full read/write access to the entire database via the MCP server tools or direct database connection strings.

### The Spin API & WASM Brain
The Spin API acts as an intermediary for the Android app and other external clients. 
- **Database Access:** Currently, the "WASM brain" (Rust components) does not have direct access to the database for all operations. The MCP server remains the primary interface for complex data manipulation.
- **Token Handling:** The Spin API honors OIDC tokens, but downstream processing often relies on the same permissive database access patterns as the MCP server.

## 2. Personal Identifiable Information (PII)

### Encryption via Master Key
The system identifies and segregates PII (Phone numbers, API tokens for third-party services like Beeminder and Clozemaster).
- **Encryption Standard:** PII is encrypted using `AES-256-GCM`.
- **The Master Key Requirement:** Access to any PII—whether from the MCP server or the Spin API—strictly requires the `MASTER_ENCRYPTION_KEY`. 
- **Vulnerability:** If the `MASTER_ENCRYPTION_KEY` is compromised or stored insecurely (e.g., in plain text in an environment variable on a shared machine), all user PII across all tenants in that database is effectively exposed.

### Data at Rest
PII is stored in an encrypted hex-string format in the `users` and `beeminder_credentials` tables. Non-PII data (steps, language completion counts, budget balances) is stored in plain text.

## 3. Multi-Tenancy and Infrastructure Isolation

### Hosting and Billing Constraints
Mecris is designed for multi-tenant logic, but it does not support multi-tenant infrastructure sharing at the database level.
- **Neon "CU" Isolation:** The Neon "Compute Unit" (CU) is a billable metric. Sharing access to a single Neon instance with untrusted users is equivalent to allowing them to incur costs on the owner's behalf.
- **Forking Requirement:** Users who wish to fork or use Mecris independently **MUST** provision their own Neon or Postgres database. We do not provide shared database access to any external parties.

### GDPR-Style Compliance Gaps (Informational)
- **Data Portability:** There is currently no implementation for a user to export their data in a machine-readable format.
- **Right to Erasure:** There is no "Delete my account" functionality. Deletion requires manual SQL intervention by the database administrator.
- **Informed Consent:** While the SMS system implements an opt-in/opt-out mechanism, there is no centralized privacy policy or consent management for the broader data collection (steps, location, study habits).

## 4. Summary of Data Access Points

| Component | Access Level | Requirement |
| :--- | :--- | :--- |
| **MCP Server** | Full DB Access | Local File Read Access |
| **Spin API** | Partial DB Access | OIDC Token |
| **PII Decryption** | High | `MASTER_ENCRYPTION_KEY` |
| **Neon Console** | Absolute | Neon Account Credentials |
