# Prompt 0 — prove the Akamai API is truly online before changing architecture

You are working in the existing `mecris` codebase. Before proposing repairs, forks, rollbacks, or another deployment, determine whether the **Akamai API is genuinely online and usable**.

Use both sources of evidence available to you:

1. **Authenticated Akamai verification:** use the already-authorized/logged-in credentials and the existing documented Akamai deployment path. Verify the canonical API base URL, TLS/routing, authentication, route behavior, dependency health, and the Android sync contract. Do not weaken OIDC, bypass auth, or print tokens/secrets.
2. **Android evidence:** inspect the Android app logs and/or the logs produced by the current Pi-harness run. Determine the exact base URL, routes, status codes, response bodies or error classes, timestamps, retries, and whether the app actually completed a sync. Distinguish “the endpoint accepted a request” from “the Android sync completed successfully.”

Run a minimal, non-destructive authenticated smoke test. Prefer read-only routes and a synthetic/authorized test account. Do not invoke all-user sync, reminders, SMS, Beeminder writes, or other side-effecting operations unless explicitly authorized.

Return a proof table:

| Claim | Evidence | Result |
|---|---|---|
| Akamai hostname resolves and terminates TLS | exact observation | pass/fail |
| API route is reachable | exact route/status/latency | pass/fail |
| authentication works | credential class and response, never the secret | pass/fail |
| database/dependencies are usable | safe authenticated read or log evidence | pass/fail/unknown |
| Android can complete the canonical sync | Android/Pi logs with timestamps | pass/fail |
| current deployment is the intended release candidate | repo/config/deployment evidence | pass/fail |

Known comparison observations (2026-07-30): the Fermyon `.fwf.app` deployment exposes `/internal/review-pump-status` with valid idle JSON, `/health` with a weak 200 response, and `/profile` with 401 without OIDC. Those observations do **not** establish Akamai availability or Android readiness. The old `glo0zpfm.fermyon.app` channel is platform-level 404, and `aka.fermyon.tech` is deprecated and must not be probed.

Do not modify production, create a fork, or tag a release in this pass. If Akamai is not proven online, identify the exact blocker and the smallest next diagnostic step.