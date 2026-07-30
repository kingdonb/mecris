# Prompt 1 — establish the deployment truth and choose the recovery target

You are working in the existing `mecris` codebase. The immediate goal is to get the existing Mecris API online again so the Android app can sync without requiring the end user to run an STDIO MCP server locally. Do not design another Mecris implementation, fork the deployment, or bisect back to the pre-`0.0.1-beta.4` API unless you can prove the current path is unrecoverable and report that as a separate decision.

First, build a factual inventory of what already exists:

1. Locate every API/service implementation and identify its runtime, entrypoint, deployment manifest, and intended role:
   - the Rust Spin API using the latest Spin SDK;
   - the Python Spin API using the latest Spin SDK;
   - the Python API server running outside Spin;
   - the API server embedded in the existing MCP-server variants;
   - any controller-runtime/controller code, if present, and whether it actually does anything.
2. Locate all deployment configuration and documentation for Fermyon Cloud, Akamai Functions, and any service mesh or gateway that follows them. Do not assume the old and new deployment paths are equivalent.
3. Identify the canonical API contract currently expected by the Android app: routes, authentication, sync operations, request/response shapes, and any version headers.
4. Identify the migration boundary introduced by the Spin 4 / Spin-SDK 6 upgrade. Record what was changed, what is known to work locally, and what is known to fail in Fermyon Cloud.
5. Check repository history and existing CI/deployment scripts before proposing code changes. Do not create a new fork or duplicate API.

Known external observations as of 2026-07-30:

- `https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app/internal/review-pump-status` returns HTTP 200 with valid idle PumpStatus JSON. This proves that a deployed `mecris-sync-v2` component is reachable, but it does not prove the database-backed sync API is healthy.
- The same deployment's `/health` returns HTTP 200 `{"status":"ok","message":"System healthy"}`. Treat this as a weak/possibly misleading signal, not proof of end-to-end health.
- The same deployment's `/profile` returns HTTP 401 without OIDC credentials, showing that at least that protected route is reachable and authentication is enforced.
- `https://mecris-sync-v2-glo0zpfm.fermyon.app/...` returns Fermyon platform-level HTTP 404 `Not Found | Fermyon Cloud`; treat that channel/app registration as unavailable, not as an application-level route failure.
- The deprecated `aka.fermyon.tech` hostname is not a target and must not be probed.

Deliverable for this first pass:

- a short deployment truth table;
- the single best existing recovery target, with evidence;
- the smallest validation or repair step that can move that target toward serving the Android API;
- blockers and missing credentials/configuration;
- a list of files you would modify, if any.

Do not modify production, rotate secrets, delete deployments, or introduce a new service in this pass. Prefer inspection, local tests, manifest validation, and a reversible smoke-test plan.