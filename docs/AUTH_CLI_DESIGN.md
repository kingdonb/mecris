# Design: Terminal-Based Authentication & CLI Login

This document outlines the implementation plan for `mecris login` and the enforcement of authentication within the Mecris MCP ecosystem.

## 1. The Terminal Authentication Prompt
When an unauthenticated session is detected (e.g., running `gemini` or `claude code` without a valid local token), the MCP server should return a clear instruction rather than failing silently or falling back to a default user.

**Post-Hardening Behavior:**
- **Request**: `get_narrator_context`
- **Response (Unauthenticated)**: 
  ```json
  {
    "error": "Authentication Required",
    "instruction": "Please run `mecris login` in a separate terminal window to authenticate your session."
  }
  ```

## 2. The `mecris login` Flow
We will implement an "AWS CLI" style OIDC flow using Pocket ID.

### A. Core Components
1. **Credentials Manager (`services/credentials_manager.py`)**: 
   - Responsible for reading/writing `~/.mecris/credentials.json`.
   - Handles Token Refresh logic (automatically using refresh token if access token is expired).
2. **Local Loopback Server**:
   - A temporary, lightweight server (using `http.server` or `fastapi`) started by the CLI to capture the OIDC redirect.

### B. The Flow
1. User runs `mecris login`.
2. CLI generates a PKCE `code_verifier` and `code_challenge`.
3. CLI starts a local server on a random port (e.g., `http://localhost:54321`).
4. CLI prints a URL and attempts to open it in the system browser:
   `https://metnoom.urmanac.com/authorize?client_id=...&redirect_uri=http://localhost:54321&...`
5. User logs in via Pocket ID (Passkey/OIDC).
6. Pocket ID redirects to `http://localhost:54321/?code=...`.
7. CLI captures the `code`, performs the token exchange (PKCE), and receives Access/Refresh tokens.
8. CLI stores the tokens and the user's `sub` (User ID) in `~/.mecris/credentials.json`.
9. CLI prints "✅ Login Successful. You are now logged in as [User ID]."

## 3. High-Priority Security Gap Remediation

### GAP 1: `DEFAULT_USER_ID` Fallback
**Fix**: Refactor all service initializations to require a `user_id`. 
- In `multi-tenant` mode, if no `user_id` is provided (via JWT or CredentialsManager), the service **must fail**.
- Remove `os.getenv("DEFAULT_USER_ID")` from constructor defaults.

### GAP 2: Unauthorized Endpoints
**Fix**: Implement a FastAPI `Depends` dependency for all sensitive routes.
```python
async def get_current_user(request: Request):
    if os.getenv("MECRIS_MODE") != "multi-tenant":
        return os.getenv("DEFAULT_USER_ID") # Standalone mode trust
    
    token = extract_token(request)
    return await validate_jwt_and_get_sub(token)
```

## 4. Immediate Next Steps
1. **Implement `CredentialsManager`** to provide a standard way to get the "Current Local User".
2. **Add `MECRIS_MODE` to `.env.example`** and enforce it in the MCP server.
3. **Add `mecris login` command stub** to `cli/main.py`.

---
*Created: Saturday, April 4, 2026*
