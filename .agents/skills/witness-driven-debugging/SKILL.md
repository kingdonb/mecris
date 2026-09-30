---
name: witness-driven-debugging
description: Method for debugging the distributed Mecris pipeline (Android app → Spin/Akamai edge → Neon Postgres → Beeminder sink) when the agent cannot cross the deploy boundary and the operator's devices and deploys are the test rig. Use when designing falsifiable debug rounds, attributing causes from timestamps, instrumenting opaque failures, writing operator runbooks, or maintaining the root-cause suspect ledger. For concrete commands, ADB recipes, and witness queries, load the mecris-edge-sync-e2e skill alongside.
---

# Witness-Driven Debugging

The agent cannot see the phone, the cloud runtime, or prod credentials. The operator is the only sensor. The method: turn every observation into a named, queryable artifact ("witness") and eliminate suspects one lap at a time.

**Companion skill:** `mecris-edge-sync-e2e` holds the concrete protocol (deploy/trigger/witness commands, helper scripts, ADB recipes, the `HttpRequestDenied` fix). This skill is the *method*; that one is the *runbook*.

## The loop (one lap = one variable)

1. **Root-cause ledger.** Write out the ordered gate list for the subsystem (see Suspect ladder). Name exactly one suspect per lap.
2. **Instrument before you fix.** If a failure surfaces as an opaque status, the next commit must make its cause visible to a sensor — persist a typed reason to the database (`last_error`-style) AND echo it in the API response. Ship instrumentation before any speculative fix. Precedent: row 8's `send: ErrorCode::HttpRequestDenied` localized the gate in one lap; a guessed fix would have missed.
3. **Falsifiable lap.** State the prediction before shipping: the artifact that proves the hypothesis (witness row N, `fetch_status='ok'`, `pushed_value≈X`) and the artifact that disproves it (which `last_error` value names which next suspect). No unfalsifiable laps.
4. **Operator runbook.** Copy-pasteable commands + expected output + a branch table ("if still Y → next suspect Z"). Agent codes/commits/pushes; operator pulls/deploys/triggers/queries/pastes. One variable per lap.
5. **Timestamp discipline (UTC).** Correlate push time, deploy completion, trigger time, row time before crediting causation. An artifact produced before the push+deploy completed is from the old build, not a failed fix. Precedent: the "row 9" lap — identical error, tight window = stale deployment, not a bad manifest.
6. **Record.** Append each lap's result to the task's design/tasks log. The ledger is the memory across context resets.

## The three witnesses (verification chain)

A sync is proven E2E only when all three line up (see `mecris-edge-sync-e2e` §2):

1. **Fresh `requested_at`** in the request queue (e.g. `helix_balance_requests`) — the doorbell rang.
2. **Execution row** in the log table (e.g. `helix_balance_log`) — `fetch_status='ok'`, expected payload, `processed_at` set.
3. **Upstream reflection** — the sink (Beeminder goal, Clozemaster) shows the new value.

For an *inversion* proof (edge-primary over the laptop leader), additionally require that the laptop-side automation (MCP/leader) was verifiably NOT running when the artifact appeared.

## Suspect ladder (Helix balance pipeline — adapt per subsystem)

Ordered cheapest-to-verify first:

1. App trigger didn't fire — 5-min cache / surgical refresh; cold-start forces it (ADB recipe in companion skill). Witness: fresh `requested_at`.
2. Edge auth — Pocket ID JWT rejected → 401 in app, nothing queued.
3. **Runtime outbound ACL** — `allowed_outbound_hosts` in `mecris-go-spin/sync-service/spin.toml`. `send: ErrorCode::HttpRequestDenied` = refused pre-DNS; no packet left. New outbound calls need an allowlist entry.
4. Platform-level outbound policy (Akamai Functions) — only after a confirmed post-fix deploy.
5. Origin response — Cloudflare 403/1010 needs the lever UA header set; 401 = token problem.
6. Token decrypt — `master_encryption_key`, `users.helix_api_token_encrypted`.
7. SQL on edge — spin-sdk pg casts (no `ParameterValue::Null`; NUMERIC via `::FLOAT8::NUMERIC`; `TO_CHAR` with quoted literals, not strftime).
8. Beeminder push — requestid dedupe: **422 = success**; unchanged value ⇒ R3 silence (no push).

## Ecosystem traps (verified in this repo)

- `spin.toml` manifests bake at deploy; a running deployment keeps the old manifest.
- Partial `--variable` lists on `spin aka deploy` **wipe omitted vars to defaults** (caused a live outage). Always deploy via `make deploy-akamai`.
- Force-stop/cold-start is a POST *trigger*, never an app update; the app is response-agnostic (additive DTO fields, Gson ignores extras — no APK rebuild for backend changes).
- Unknown balance is never $0: failed fetches log `'failed'`, push nothing.
- Beeminder never feeds governor decisions (R8: a sink is a sink).
- Test suite has ~23 pre-existing baseline failures — never chase them.

## Operator contract

- Ask, never guess, at install/deploy gates.
- Tokens never in chat; Beeminder token pasted in app settings only.
- Tell the operator the expected output *before* they run it, so a mismatch is instantly visible.
