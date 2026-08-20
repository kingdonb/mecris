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

### 2. Create Release Branch & Bump Version

Create a release branch from `main`:
```bash
git checkout main && git pull origin main
git checkout -b release/v0.0.1-rc.4
```

Use the official version bump script (updates 15+ version strings across the repo, including Android `versionCode` via `VC=nn`):

```bash
make bump-version VERSION=0.0.1-rc.4 VC=28
```

This updates:
- `VERSION_MANIFEST.json`
- `mecris-go-project/app/build.gradle.kts` (Android `versionName` + `versionCode`)
- `boris-fiona-walker/spin.toml` (Spin/WASM)
- `mecris-go-spin/sync-service/spin.toml` (Spin/WASM)
- `pyproject.toml` (Python)
- `uv.lock` (Auto-synchronized via `uv lock`)
- `web/package.json` (Web)
- `ROADMAP.md` (version label + date)

### 3. Commit, Push Branch & Open PR (Branch Protection)

Because `main` is protected with mandatory CI checks, releases must go through a pull request:

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

git commit -m "chore(release): bump version to 0.0.1-rc.4 + VC=28"
git push origin release/v0.0.1-rc.4

# Open PR using GitHub CLI
gh pr create --title "chore(release): release v0.0.1-rc.4" --body "Release preparation for v0.0.1-rc.4 (VC=28)." --base main
```

### 4. Merge PR to Main

Wait for CI to pass on the PR, then merge to `main`:

```bash
gh pr merge --squash --auto
# Or merge once green:
gh pr merge --squash --delete-branch
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
- `mecris-go-release-unsigned.apk`
- `wasm-components.tar.gz`

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