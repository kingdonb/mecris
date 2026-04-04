# Security Audit Report: Mecris Personal LLM Accountability System
**Date:** April 4, 2026
**Auditor:** Gemini (Mecris Senior Architect)
**Status:** CRITICAL GAPS IDENTIFIED

## 1. Executive Summary
The Mecris system has made significant strides in migrating to a multi-tenant Neon (Postgres) backend. However, an audit of the application layer—specifically the Python MCP server and its associated FastAPI endpoints—reveals a pervasive "single-tenant mindset." While high-value credentials (like API tokens) are encrypted, significant amounts of Personally Identifiable Information (PII) remain in plaintext. Furthermore, the primary API endpoints are entirely unauthorized, relying on local environment variables to infer user identity. This creates a severe disparity in security posture between the cloud-facing Rust components (which enforce JWT validation) and the local Python server.

## 2. PII & Data Encryption Audit
The system employs `AES-256-GCM` via an `EncryptionService`. This is successfully used to protect critical authentication tokens. However, its usage is incomplete.

### **Encrypted Fields (Secure)**
- `users.beeminder_token_encrypted`
- `users.beeminder_user_encrypted`
- `users.clozemaster_email_encrypted`
- `users.clozemaster_password_encrypted`
- `users.phone_number_encrypted`

### **Vulnerabilities: Plaintext PII**
The following fields represent a significant privacy risk in a multi-tenant or compromised environment:

| Table | Column | Risk Level | Description |
| :--- | :--- | :--- | :--- |
| `message_log` | `content` | **CRITICAL** | Stores the full, unredacted text of all SMS and WhatsApp communications sent and received. |
| `walk_inferences` | `gps_route_points` | **HIGH** | Stores precise location telemetry and routing data. |
| `usage_sessions` | `notes` | **MEDIUM** | Stores LLM interaction context, which may inadvertently contain personal thoughts, code, or private data. |
| `autonomous_turns` | `output` | **MEDIUM** | Detailed logs of agent actions, tool outputs, and results. |
| `users` | `notification_prefs` | **LOW** | Stores personal schedules, sleep windows, and threshold settings as plaintext JSONB. |

**Auditor's Note:** To achieve true multi-tenancy and data safety, the critical and high-risk fields must be migrated to encrypted storage.

---

## 3. Endpoint Authorization Audit
The `mcp_server.py` exposes several FastAPI endpoints designed to serve the "Majesty Cake" UI and internal status monitoring tools. 

### **Vulnerabilities: Unauthorized Access**
The following endpoints require **absolutely no authentication**:
- `GET /narrator/context`: Returns the full strategic status, including all active goals, pending todos, budget status, and physical activity status.
- `GET /beeminder/status`: Returns detailed Beeminder goal data, including runway and derailment risks.
- `GET /budget/status`: Returns financial data regarding LLM token spend, remaining balance, and daily burn rates.
- `POST /intelligent-reminder/trigger`: An unauthenticated trigger that initiates notification logic.

**Impact:** Any entity with network access to the server (default port 8000) can scrape the user's entire strategic, financial, and behavioral state. 

---

## 4. Identity & Multi-Tenancy Logic
The system's approach to multi-tenancy is currently "opt-in" rather than structurally enforced, leading to critical identity assumption flaws.

### **The `DEFAULT_USER_ID` Fallback Trap**
Throughout the Python service classes (`UsageTracker`, `NeonSyncChecker`, `VirtualBudgetManager`, `scheduler`), the codebase implements a dangerous fallback pattern:
```python
self.user_id = user_id or os.getenv("DEFAULT_USER_ID")
```
**Why this is critical:**
1. Because the FastAPI endpoints lack authentication, they pass `user_id=None` to the backend services.
2. The services immediately fall back to the `DEFAULT_USER_ID` defined in the server's `.env` file.
3. Consequently, unauthenticated requests automatically resolve to the system administrator's personal data. 

This masks authorization failures, making the system appear functional for a single user while completely circumventing multi-tenant data isolation.

### **Architectural Inconsistency**
There is a severe split-brain in the project's security architecture:
- **Rust Components (`sync-service`):** Implement robust cryptographic JWT signature verification (via JWKS) and reject unauthorized requests.
- **Python Components (`mcp_server.py`):** Rely on "Dotfile Security" (local environment variables), bypassing JWT checks entirely.

## 5. Auditor's Conclusion
While Mecris has the foundation of a secure system (Neon row-level isolation, `EncryptionService`), the Python application layer actively undermines these protections for convenience. The system is currently insecure for anything other than local, single-user operation on a trusted network. 

To prepare for mass adoption and secure cloud deployments, the system must formally distinguish between a "Local Standalone" deployment and a "Cloud Multi-Tenant" deployment, enforcing strict JWT authorization and comprehensive encryption for the latter.
