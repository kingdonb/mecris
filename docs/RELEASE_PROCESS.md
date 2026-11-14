# Mecris Release Process

> **Note**: Main branch is now protected with mandatory CI checks. All releases must go through PR with successful CI before merging.

## Version Tagging Convention

**All releases MUST use the `v` prefix:** `v0.0.1-rc.4`, `v0.0.1-beta.10`, `v1.0.0`, etc.

The GitHub Actions Release workflow triggers on:
```yaml
on:
  push:
    tags:
      - 'v*'
      - '0.*'
```

While `0.*` would match `0.0.1-rc.4`, **always use `v0.0.1-rc.4`** to:
- Match existing tag history (`v0.0.1-rc.3`, `v0.0.1-beta.*`)
- Ensure consistent GitHub Release naming
- Avoid confusion with branch names or other refs

---

## Release Procedure

### 1. Pre-Release Validation

```bash
# Run full test suite (Python + Rust)
make test

# Or specifically:
make test-python
make test-rust
```

All tests must pass. CI must be green on `main`.

### 2. Bump Version on PR / Release Branch

You can release directly from an active PR branch (to avoid redundant CI runs) or create a dedicated release branch:

```bash
# Option A: Direct from active feature/fix PR branch (Recommended for faster turnaround)
# Simply apply the bump directly on the working branch before merging.

# Option B: Dedicated release branch from main
git checkout main && git pull origin main
git checkout -b release/v0.0.2
```

Use the official version bump script (updates 15+ version strings across the repo, including Android `versionCode` via `VC=nn`):

```bash
make bump-version VERSION=0.0.2 VC=33
```

This updates:
- `VERSION_MANIFEST.json`
- `mecris-go-project/app/build.gradle.kts` (Android `versionName` + `versionCode`)
- `boris-fiona-walker/spin.toml` (Spin/WASM)
- `mecris-go-spin/sync-service/spin.toml` (Spin/WASM)
- `mecris-go-spin/sync-service/Cargo.toml` and `Cargo.lock` (the version `GET /version` reports)
- `pyproject.toml` (Python)
- `uv.lock` (Auto-synchronized via `uv lock`)
- `web/package.json` (Web)
- `ROADMAP.md` (version label + date)

### 3. Commit, Push & Run CI (1st CI Run: Before Merge)

Commit and push the version bump to the PR branch:

```bash
git add VERSION_MANIFEST.json \
        mecris-go-project/app/build.gradle.kts \
        boris-fiona-walker/spin.toml \
        mecris-go-spin/sync-service/spin.toml \
        pyproject.toml \
        uv.lock \
        web/package.json \
        ROADMAP.md \
        docs/RELEASE_PROCESS.md

git commit -m "chore(release): bump version to 0.0.2 + VC=33"
git push origin <branch-name>
```

Wait for CI to run and pass on the PR. Mandatory checks run automatically.

### 4. Merge PR to Main

Wait for CI to pass on the PR, then merge to `main`:

```bash
# Squash merging is disabled for this repository (since 2026-11-13). Use a merge commit.
gh pr merge --merge --delete-branch
```

### 5. Tag and Push Release on Main

Once merged to `main`, checkout updated `main`, tag, and push the tag (**Critical: Use `v` prefix**):

```bash
git checkout main
git pull origin main

git tag v0.0.1-rc.4
git push origin v0.0.1-rc.4
```

### 6. Monitor Release Workflow

The GitHub Actions Release workflow will:
1. Build Android APK (`mecris-go-project`)
2. Build WASM components (sync-service, boris-fiona-walker, etc.)
3. Publish GitHub Release with artifacts

Watch progress:
```bash
gh run watch --repo kingdonb/mecris
```

### 7. Verify Release

Check: https://github.com/kingdonb/mecris/releases/tag/v0.0.1-rc.4

Assets should include:
- `mecris-go-release-unsigned.apk` (unsigned: do **not** install it as is, see section 9)
- `wasm-components.tar.gz`

The workflow publishes the release as a **pre-release**. It becomes Latest only after the phone test (section 10).

Both assets carry SLSA v1 build provenance from a GitHub-hosted runner (Build Level 2; Level 3 is #357). To check an asset you downloaded:

```bash
gh attestation verify mecris-go-release-unsigned.apk -R kingdonb/mecris
gh attestation verify wasm-components.tar.gz -R kingdonb/mecris
```

---

### 8. Migrate, deploy the Spin API and recreate the crons (a tag is not a deploy)

**8a. Migrations, with the owner's OK.** If the release adds `scripts/migrate_*.py` files, run them against live Neon **before** the deploy, so the new code finds its columns. Each must be additive and safe to run twice. Never run one without the owner's explicit OK.

**8b. Deploy.** The release workflow builds the Wasm bundle and attaches it to the GitHub Release. **Nothing deploys it.** The Spin API is deployed by hand from a machine on the home network, because the build needs the private JWKS endpoint.

```bash
# .env must define INTERNAL_API_KEY and TWILIO_WHATSAPP_FROM (see mecris-go-spin/DEPLOYMENT.md)
./mecris-go-spin/sync-service/deploy-akamai.sh

# Tests as the callers do, and waits until the new version is actually serving
./scripts/verify_spin_deploy.sh
```

`spin aka app status` shows `Rolling Out` for a minute or two after the deploy command returns, and the old version answers during that time. Do not hand-test until the check script reports the new version.

**The check must not send WhatsApp.** Read the script's usage line before running it. The v0.2.0 script ends with a real cron-shaped `trigger-reminders` call, which sends a reminder when run inside the window; with that version, pass `--no-trigger`. From v0.3.0 the default is a dry run and a real send is opt-in.

**8c. Crons.** Akamai cron can only carry the key in the query string, so the jobs must be recreated whenever `INTERNAL_API_KEY` rotates or the schedule changes:

1. List the jobs with `spin aka cron list`. It prints the key: never paste its output anywhere.
2. Delete the jobs the script will recreate, and any retired ones, with `spin aka cron delete <name>`.
3. Run `./scripts/setup_spin_cron.sh`, then `spin aka cron list` again to confirm the names and schedules.

If cloud reminders were paused (as they were after v0.2.0), only recreate `trigger-reminders` once 8b has passed.

**8d. Watch before you trust it.** Before the phone install, watch at least three cron cycles in `message_log` and the pulse (metadata only, never message contents): every run leaves a record, and no WhatsApp nag goes out outside the window, within 4 hours of another nag, while the phone's heartbeat is fresh, or beyond the daily cap.

### 9. Install the Android build (never the unsigned asset)

The release APK, `mecris-go-release-unsigned.apk`, is **unsigned**. Android will not install it over the app on the phone, which is signed with the debug key from Android Studio. The way out it offers, uninstalling the app first, **wipes the app's data** (sign-in, preferences, local history). **Never install the unsigned asset, and never accept an uninstall prompt.**

Install one of these instead; both keep the same signing key, so the update installs in place:

- **(a) Debug build at the tag, from Android Studio** (preferred):
  ```bash
  git fetch --tags && git checkout v0.3.0
  ```
  Open `mecris-go-project` in Android Studio on the same machine (same `~/.android/debug.keystore`), pick the `debug` variant and Run on the phone.
- **(b) Sign the release asset locally with that same debug key:**
  ```bash
  zipalign -p -f 4 mecris-go-release-unsigned.apk mecris-go-aligned.apk
  apksigner sign --ks ~/.android/debug.keystore --ks-key-alias androiddebugkey \
    --out mecris-go-signed.apk mecris-go-aligned.apk   # prompts for the keystore password
  adb install -r mecris-go-signed.apk
  ```

Then check the installed version and backend:

```bash
adb shell dumpsys package com.mecris.go | grep versionCode
```

In the app, the backend should read Akamai Cloud. If Android shows an uninstall or "conflicting package" prompt, stop: the key does not match.

The app and the API do not have to ship together: an older app keeps working against a newer API. When a release changes what the phone asks of the cloud, install the app only after the cloud side has passed 8b and 8d.

**Current status (2026-11-14): do not install the 0.2.0 APK (versionCode 40).** v0.2.0's cloud reminders went out at the wrong hours, and the app's VERIFY flow cannot parse the Spin API's verification replies (#369). VC 41 (v0.3.0) waits for the cloud fix: install it only after v0.3.0's Spin deploy has passed the dry-run check and three clean cron cycles. Until then, keep the installed VC 39 and do not tap VERIFY.

### 10. Promote to Latest after the phone test

Once the phone checks for the release pass on the installed build, promote the pre-release:

```bash
gh release edit v0.3.0 --prerelease=false --latest
```

Until then it stays a pre-release, so nobody mistakes an untested build for the current one.

---

## Common Mistakes to Avoid

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| Tag `0.0.1-rc.4` (no `v`) | Release works but inconsistent with history | Delete tag, retag with `v` prefix |
| Skip `make bump-version` | Version strings out of sync | Always use the script |
| Direct push to `main` | Rejected by branch protection | Use a release PR branch |
| Forget `VC=nn` for Android | `versionCode` not incremented in APK | Specify `VC=nn` in `make bump-version` |
| Push tag before merging version bump to `main` | Release built with old version | Merge PR to `main` first, then tag `main` |
| Forget to run tests | Broken release | `make test` must pass |
| Treat the tag as a deploy | The live API still runs the previous version | Run `deploy-akamai.sh`, then `scripts/verify_spin_deploy.sh` |
| Test right after `spin aka deploy` returns | The old version answers during rollout and results mislead | Let `verify_spin_deploy.sh` wait for the new version |
| Install `mecris-go-release-unsigned.apk`, or accept an uninstall prompt | The app's data is wiped | Install a debug build at the tag, or sign the asset with the same debug key (section 9) |
| Run the deploy check with a real trigger inside the window | A real WhatsApp reminder goes out | Use the dry run (section 8b) |
| Mark the release Latest before the phone test | An untested build looks current | Promote only after section 10's checks |

---

## Rollback if Needed

If a release is pushed with wrong version:

```bash
# Delete release (auto-deletes tag) or:
gh release delete v0.0.1-rc.4 --yes
git tag -d v0.0.1-rc.4
git push origin :refs/tags/v0.0.1-rc.4

# Fix version on a branch, open PR, merge, retag
make bump-version VERSION=0.0.1-rc.5 VC=29
```

---

## Files That Define Versions

| File | Component | Notes |
|------|-----------|-------|
| `VERSION_MANIFEST.json` | Master manifest | All components listed |
| `pyproject.toml` | Python package | `version = "..."` |
| `uv.lock` | Python lockfile | Auto-locked via `uv lock` |
| `mecris-go-project/app/build.gradle.kts` | Android | `versionName`, `versionCode` |
| `mecris-go-spin/sync-service/spin.toml` | Spin sync-service | `version = "..."` |
| `boris-fiona-walker/spin.toml` | Spin walker | `version = "..."` |
| `web/package.json` | Web UI | `"version": "..."` |
| `ROADMAP.md` | Documentation | Version label + date |

**Never edit these manually.** Always use `make bump-version VERSION=x.y.z`.

---

## CI/CD Reference

- **CI (PRs/main pushes)**: `.github/workflows/ci.yml` — runs full test suite + Spin server
- **E2E Pi+Mecris**: `.github/workflows/e2e-pi-mecris.yml` — tests Pi extension
- **Release (tag pushes)**: `.github/workflows/release.yml` — builds artifacts, publishes release

The release workflow only runs on tag push — merging to main does NOT trigger it.
---

## Canonical Releases and Repository Designation

**Canonical repository**: `kingdonb/mecris` (primary, protected `main` branch).
**User/fork repository**: `yebyen/mecris` (same operator; fork for development/workflow isolation).

This distinction is intentional: the user (`yebyen`) operates through the fork for autonomous agent turns (`mecris-bot` workflow, Pi harness extensions, session logs), while releases, CI triggers, and production artifacts are published from the canonical repo (`kingdonb/mecris`). Both repositories are controlled by the same operator; the separation is architectural, not organizational.

### Verified Releases (as of this document's last update: 2026-11-14)

| Tag | Date | Canonical Repo | Source PR | Notes |
|-----|------|---------------|-----------|-------|
| `v0.0.1` (historical) | Prior releases | `kingdonb/mecris` | Previous releases | Base version for project initialization |
| `v0.0.2` | 2026-08-20 | `kingdonb/mecris` | Previous release cycle | Pre-transition version |
| `v0.0.3` | 2026-09-06 | `kingdonb/mecris` | PR `#297` (fix), PR `#298` (release) | Restores ghost heartbeat via REST API; updates all 15+ version references (`VERSION_MANIFEST`, Android `VC=34`, Spin, web, Python, docs, `ROADMAP.md`) |
| `v0.1.0` | 2026-09-30 | `kingdonb/mecris` | PR `#330` (feature), PR `#331` (release) | Helix balance odometer (task 588, edge-primary), all version refs synced, Android VC=35 |
| `v0.1.1` | 2026-09-30 | `kingdonb/mecris` | PR `#332` | R3 change-gate oscillation fix (15 duplicate overnight datapoints); all version refs synced, Android VC=36 |
| `v0.1.2` | 2026-10-01 | `kingdonb/mecris` | PR `#333` | Constructive interference: review pump honors Beeminder due-today road math; all version refs synced, Android VC=37 |
| `v0.1.3` | 2026-10-01 | `kingdonb/mecris` | PR `#334` | Beeminder safebump & epoch road fix; constructive interference verified live (160 due), Android VC=38 |
| `v0.1.4` | 2026-10-04 | `kingdonb/mecris` | PR `#335` | Battery diet: background 8 hr 11 min → target ≤ ~2.5 hr/day (heartbeat 15→60 min w/ UPDATE policy, ET quiet-hours gate, helix-balance ≤ 1/hr throttle, cheap-first nag worker, WORKER_METRIC instrumentation); calendar-rot CI test fix; Android VC=39 |
| `v0.2.0` | 2026-11-14 | `kingdonb/mecris` | PR `#375` | Public `GET /version`, post-deploy check script; Android VC=40. **Do not install its APK**: cloud reminders went out at the wrong hours (#369) |

**Note**: This table reflects releases verified at the time of this document's creation. For the most current release state, consult `VERSION_MANIFEST.json`, the `main` branch tags (`v*`), and the active PR list on `kingdonb/mecris`. This document is evergreen — it is not guaranteed to remain up-to-date without manual verification.

**Reference**: Issue `#340` (ghost heartbeat discovery) and decision `2026-09-06-ghost-heartbeat-restoration` document the mechanism change (direct Neon DB → REST API via `localhost:8000/heartbeat`) that enabled the `v0.0.3` restoration.
