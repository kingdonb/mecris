# Prompt 3 — restore the existing API with the smallest viable change

Using the inventory and recovery target from Prompt 0/1, restore the existing canonical Mecris API. The priority is service availability for Android synchronization, not feature parity across every historical implementation.

Rules:

- Do not create another Mecris fork.
- Do not revive or maintain the old pre-`0.0.1-beta.4` implementation merely because it is familiar.
- Do not add a new controller-runtime controller, gateway, MCP variant, or parallel API unless an existing deployment contract explicitly requires it.
- Do not make Fermyon Cloud the target if the current Spin-SDK 6 deployment cannot run there; document that limitation and use the already-supported current target instead.
- Preserve the existing Android API contract where possible. If a route or response must change, show the before/after contract and identify the Android-side consequence.
- Keep OIDC and internal authentication fail-closed. Never disable auth for a smoke test in a deployed environment.
- Never print, commit, or paste secrets, tokens, database URLs, encryption keys, or internal API keys.

Work in this order:

1. Make the smallest source/configuration repair needed for the selected existing deployment.
2. Run the repository's existing tests, type checks, formatting, and build/deployment validation.
3. Deploy only through the existing documented mechanism and only when the target/credentials are already available.
4. Verify a safe unauthenticated liveness route, then verify protected routes with an authorized test identity or service credential. A protected 401/403 is evidence that routing/auth is alive; it is not an application failure.
5. Exercise the smallest non-destructive Android sync path with a synthetic or authorized test account. Avoid triggering all-user sync, reminders, SMS, or Beeminder writes unless explicitly authorized.
6. Report exactly what is online, what is not, what was changed, and what remains blocked.

Success means the Android app can use the canonical API without the end user running an STDIO MCP server. It does not mean every historical API implementation is deployed or every old Fermyon channel is restored.