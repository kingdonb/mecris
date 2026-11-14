# Next Session: land v0.3.0 (prove the cloud arm), then install VC 41

## Current Status (2026-11-14)

- v0.2.0 is tagged and deployed to Akamai (Spin API). It sent five WhatsApp walk reminders on 2026-11-14 at the wrong hours: the gates ignore `notification_prefs`, and two Postgres type traps break the cooldown and the Android stand-down (#369).
- The `trigger-reminders` Akamai cron is **paused** (deleted) until v0.3.0 deploys. The failover-sync crons still run.
- **Do not install the 0.2.0 APK**, and do not tap VERIFY in the app until v0.3.0 is deployed: Spin's verification replies are not JSON objects yet.
- v0.3.0 is planned in epic #360 as seven PRs plus the release PR: localhost-bridge, contracts, hygiene, spin-cloud-arm, truthful-narrator (Python MCP), android, spin-status, then release. Merge with merge commits; `main` is PR-protected.
- Claude runs on the Ultra plan (subscription grant to about 2027-05-13). Usage credits stay off.

## Verified This Session

In the hygiene-docs PR (chore/v0.3-hygiene):

- [x] Root one-offs, dated docs and screenshots archived under `attic/` with `git mv` (#347, #348); `poc/v6-hello/target/` untracked.
- [x] The personal number committed in two tracked files was replaced with a Twilio magic number; `tests/test_no_personal_numbers.py` now guards every tracked file (#358).
- [x] Renovate holds Python below 3.15 and ignores mcp majors (#218). JSON-checked only: confirm the next Dependency Dashboard refresh shows no config error.

## Pending Verification (Next Session)

- [ ] Merge in this order once each is green: `fix/v0.3-localhost-bridge`, `chore/v0.3-contracts`, `chore/v0.3-hygiene`, `fix/v0.3-spin-cloud-arm`, `fix/v0.3-truthful-narrator`, `feat/v0.3-android`, `feat/v0.3-spin-status`, then the release PR.
- [ ] Before the deploy, with the owner's OK: run the additive migrations on live Neon (`scripts/migrate_v9_*.py`).
- [ ] Deploy from the home network: `./mecris-go-spin/sync-service/deploy-akamai.sh`, then `./scripts/verify_spin_deploy.sh` (it must send no WhatsApp; check its usage line first).
- [ ] Recreate the crons with `./scripts/setup_spin_cron.sh` after deleting the old ones; confirm with `spin aka cron list` without pasting its output (it prints the key).
- [ ] Watch at least 3 cron cycles in `message_log` (metadata only): no WhatsApp nag outside 14:00-17:59 New York, within 4 h of another nag, while the phone heartbeat is fresh, or beyond 3 a day.
- [ ] In the installed app, VERIFY the phone once; expect a 'sent' and then a 'received' phone_verification row and `phone_verified = true`.
- [ ] After 3 clean cycles: install VC 41 from Android Studio at tag v0.3.0 (debug variant, same debug key, decline any uninstall prompt). See `docs/RELEASE_PROCESS.md` section 9.
- [ ] After a 3-day `message_log` watch and the phone checks: promote v0.3.0 to Latest (`docs/RELEASE_PROCESS.md` section 10).
- [ ] With the owner's dates: one `update_budget` call to switch the budget row to the Ultra subscription; then `get_narrator_context` should show `Claude: Ultra until …` with no budget nag.
- [ ] Optional, needs the owner's OK: `python scripts/fetch_template_bodies.py` (read-only Twilio Content API) to commit `data/templates/*.json` for #363.

## Infrastructure Notes

- Cron: `trigger-reminders` paused; `failover-sync-edt` and `failover-sync-est` still active until v0.3.0 replaces them with one `5 */2 * * *` job.
- The MCP bridge listens on 0.0.0.0:8080 until v0.3.0 makes it loopback-only (#39). Stop leftover `mcp_server.py` processes after the merge.
- The release APK is unsigned. Never install it over the debug-signed app and never accept an uninstall: that wipes the app's data.
- `deploy-fermyon.sh` and `spin.fermyon.toml` stay until boris-fiona-walker is retired; the Makefile still calls them.
- Owner decisions still open: a git history rewrite (the old number and the 219 MB target tree are still in history), whether `tools/kev/` goes into `.gitignore`, and whether `cron_reminder_check.sh` is still in the crontab.
