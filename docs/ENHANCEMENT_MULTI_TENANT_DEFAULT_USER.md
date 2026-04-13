# Enhancement: Local Default User in Multi-Tenant Mode

## The Problem
Currently, when `MECRIS_MODE` is set to `multi-tenant`, the system disables all local credential fallback logic. This is intended to prevent security leaks in a public cloud environment, but it creates excessive friction for local operators and agents.

If an agent or human operator has successfully run `mecris login` on their local machine, their `user_id` is stored in `~/.mecris/credentials.json`. However, the MCP server ignores this file in multi-tenant mode, resulting in "Authentication Required" errors unless the `user_id` is explicitly passed to every tool call.

## Proposed Fix
Modify `services/credentials_manager.py` to allow falling back to the local credentials file even in `multi-tenant` mode, provided that:
1. No explicit `provided_user_id` was passed to the function.
2. The code is running in a context where local file access is permitted (which is always true for the current architecture).

## Implementation Detail
Update `CredentialsManager.resolve_user_id` in `services/credentials_manager.py`:

```python
    def resolve_user_id(self, provided_user_id: Optional[str] = None) -> Optional[str]:
        # 1. Trust explicit provided ID
        if provided_user_id:
            return provided_user_id

        # 2. Always try to fallback to local credentials if they exist
        creds = self.load_credentials()
        if "user_id" in creds:
            return creds["user_id"]

        # 3. Mode-based fallback for new/unauthenticated users
        current_mode = os.getenv("MECRIS_MODE", "standalone")
        if current_mode == "standalone":
            # ... existing logic to generate local ID ...
```

This ensures that a logged-in user is always the "default" for local operations, regardless of the multi-tenancy setting.
