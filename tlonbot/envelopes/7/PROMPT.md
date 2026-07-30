# Prompt 5 — final handoff/report format

Return a concise report with these sections:

1. **Canonical target** — which existing API/deployment is the intended path and why.
2. **Online now** — exact base URL(s), route(s), status codes, and what each observation proves.
3. **Not online / misleading** — distinguish platform 404, route 404, auth 401/403, application 5xx, timeout, and weak health responses.
4. **Changes made** — files, commits, deployment actions, and tests. Say "none" when none.
5. **Android sync readiness** — ready, partially ready, or blocked; name the exact blocker.
6. **Next smallest step** — one reversible action, not a new architecture.
7. **Safety** — confirm that no secrets were exposed and no all-user side-effecting operation was run.

Do not claim the service is healthy merely because `/health` returns 200. Do not claim the database-backed API is healthy merely because `/internal/review-pump-status` returns 200. Separate component liveness from end-to-end sync readiness.