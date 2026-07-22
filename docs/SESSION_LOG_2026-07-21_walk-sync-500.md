# Session Log: Diagnosing the Walk-Sync 500 / Beeminder `bad_token`

**Date:** 2026-07-21
**Human:** yebyen
**Primary Model:** Opus 4.8 (via Pi coding agent)
**Symptom:** Android app (`com.mecris.go`) `MecrisDashboard` → `Sync failed with code: 500`

---

## Summary

The Android dashboard was throwing **500 errors on sync**, and the MCP narrator
context reported a Beeminder **`401 bad_token`** on the `bike` goal plus
**"Missing data"** for Arabic/Greek review aggregates — even though the reviews
had actually been completed.

Root cause: the **long-running MCP server process was operating with a
stale/broken environment**. Fresh code run against the same database and
`.env` worked perfectly. A **restart of the server resolved everything** and
syncs are healthy again.

---

## Investigation Timeline

1. **Narrator context** showed:
   - Beeminder `401 bad_token` on `bike` (walk goal), `"cached": false`
   - Arabic/Greek aggregates: `"Missing data"` / reader errors
   - 0/5 daily goals despite the human reporting reviews were done

2. **Are we keeping logs?** → **No.**
   - `mcp_server.py` uses `logging.basicConfig(level=ERROR, stream=sys.stderr, force=True)`.
   - No `FileHandler` → nothing persisted to disk.
   - Level `ERROR` → `logger.info` breadcrumbs never emit.
   - The running process's stderr was attached to its **launch terminal**, so the
     500 traceback printed there and was lost.
   - All repo `*.log` files were stale; `logs/` held only old test reports.

3. **Reproduced endpoints in-process** (fresh Python loading `.env`):
   - Beeminder `bike` activity → ✅ "No walk detected today" (no 401)
   - `LanguageSyncService.sync_all()` → ✅ success
   - Clozemaster confirmed reviews **were** completed today (Arabic + Greek)
   - Everything the running server reported as broken worked from a fresh process.

4. **Database health:** `neon_connected: true`; `walk_inferences` had the expected
   unique constraint on `(user_id, start_time)` and a FK to `users`. Upsert path
   was fine. However **52 walk rows were stuck in `logging` status** — inserted
   but never advanced to `logged` because the background push to Beeminder was
   failing (consistent with the bad token).

---

## Root Cause

The Beeminder credential loader decrypts a per-user token from Neon using the
master encryption key, and **falls back to a legacy environment token if
decryption fails**. In the running (stale) process, decryption was failing, so
it fell back to a **revoked legacy token → Beeminder `401 bad_token`**. The same
decryption failure explains the "Missing data" language aggregates.

A **fresh process** loaded the correct environment, decrypted successfully, and
worked — which is why in-process reproduction always passed. **Restarting the
server** brought the process back to a good environment and sync recovered.

> Note: secret variable *names and values* are intentionally omitted from this
> log to avoid committing sensitive material.

---

## Outcome

- ✅ Server restarted by human → syncs working again.
- ✅ Human's goal completion vindicated (reviews were genuinely done; only the
  walk was skipped).
- ✅ Stuck `logging` walks expected to flush on subsequent healthy syncs.

---

## Recommendations

### High priority
- [ ] **Add a persistent rotating file log handler** (e.g. `logs/mecris_server.log`)
      at `INFO` level, in addition to stderr. This single change would have
      answered "can you see the error?" instantly. Losing tracebacks to a
      terminal is the reason this took reproduction work.
- [ ] **Make the Beeminder legacy-token fallback loud.** A decryption failure
      currently degrades *silently* to a stale/revoked token, surfacing only as a
      downstream `401`. Log an explicit `ERROR` when falling back so the true
      cause (bad/missing encryption key in the process env) is obvious.

### Medium priority
- [ ] **Fail fast on missing encryption key at startup.** If the process can't
      decrypt credentials, that should be a visible, fatal-or-alerted startup
      condition — not a per-request silent fallback.
- [ ] **Surface the 500 detail to the Android client / a server-side breadcrumb.**
      The endpoints already `raise HTTPException(500, detail=str(e))`, but the
      client only logged the status code. Capture the detail somewhere durable.
- [ ] **Reconcile stuck `logging` walks.** Add a periodic sweep (or startup check)
      that reports/retries `walk_inferences` rows left in `logging` beyond a
      threshold, so a future auth outage doesn't silently strand data.

### Lower priority / hygiene
- [ ] Consider **removing or clearly deprecating the legacy Beeminder env token**
      so it can't mask a real credential-decryption failure.
- [ ] Consider **service/process supervision** (systemd or equivalent) so restarts
      always carry the correct environment, reducing "how did that happen?"
      stale-env incidents.

---

## Attribution

**Diagnosis:** Opus 4.8 (via Pi coding agent)
**Human direction, restart, verification:** yebyen
**Mecris framework:** kingdonb/mecris (Gall-loop skills, MCP tools)
