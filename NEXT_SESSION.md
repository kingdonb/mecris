# 📅 Next Session Goals: March 22-23, 2026

## 🛡️ Security & Auth Expansion
- **User-Scoped Secrets API**: Implement authenticated endpoints to allow users to update their own Beeminder/Clozemaster tokens without manual .env edits.
- **Beeminder OAuth Flow**: Transition away from static tokens to a proper OAuth2 flow for Beeminder.
- **Token Encryption**: Implement AES-256-GCM encryption for user tokens stored in the Neon DB.

## 🔄 Integration Enhancements
- **Stateless MCP Refactoring**: Continue refactoring MCP tools to accept OIDC tokens or context directly, reducing reliance on local state.
- **Android "Dark" Alerts**: Verify the cooperative worker monitor job correctly alerts when the phone heartbeat is missing for > 4 hours.

## 🐕 Accountability
- Monitor the 1 PM walk window.
- Check Greek/Arabic Review Pump velocity for the new week.
