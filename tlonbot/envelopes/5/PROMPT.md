# Prompt 3 — between scheduled health checks

This is a maintenance/recovery check between the Wednesday and Friday OpenClaw checks. Inspect the current `mecris` repository and deployment state, then work only on the smallest reversible step that improves the availability or observability of the existing canonical API.

Start by checking whether the previous recovery attempt changed the truth table. Do not trust `/health` alone. Use the known Mecris route structure:

- `/internal/review-pump-status`: safe component liveness signal when it returns valid JSON;
- `/profile`, `/aggregate-status`, `/budget`, `/languages`, `/walks`, and other sync-service routes: protected application routes; 401/403 without credentials means the service is reachable and auth is active;
- `/internal/failover-sync` and `/internal/trigger-reminders`: never invoke without explicit authorization because they can have side effects; an unauthenticated 401/403 check is sufficient;
- `/internal/weather-heuristic`: report reachability and whether it is still a hard-coded/unimplemented stub; do not treat it as proof of live weather or GPS behavior;
- `/health`: record it, but classify it as weak unless it verifies real dependencies;
- platform-level Fermyon "application not found" responses: report the deployment channel as unavailable.

Do not probe the deprecated `aka.fermyon.tech` hostname. Do not send secrets. Do not attempt auth bypasses. Do not create another implementation or fork. If the canonical API is not yet deployable, produce the next concrete blocker and the smallest test that would resolve it. If it is online, verify the Android sync contract using a safe authorized test and report latency, status, auth behavior, and any dependency failure.