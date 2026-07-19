# Mecris Release Process

## Version Tagging Convention

**All releases MUST use the `v` prefix:** `v0.0.1-rc.2`, `v0.0.1-beta.10`, `v1.0.0`, etc.

The GitHub Actions Release workflow triggers on:
```yaml
on:
  push:
    tags:
      - 'v*'
      - '0.*'
```

While `0.*` would match `0.0.1-rc.2`, **always use `v0.0.1-rc.2`** to:
- Match existing tag history (`v0.0.1-rc.1`, `v0.0.1-beta.*`)
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

### 2. Bump Version

Use the official version bump script (updates 15+ version strings across the repo):

```bash
make bump-version VERSION=0.0.1-rc.2
```

This updates:
- `VERSION_MANIFEST.json`
- `mecris-go-project/app/build.gradle.kts` (Android)
- `boris-fiona-walker/spin.toml` (Spin/WASM)
- `mecris-go-spin/sync-service/spin.toml` (Spin/WASM)
- `pyproject.toml` (Python)
- `web/package.json` (Web)
- `ROADMAP.md` (version label + date)

### 3. Commit Version Bump

```bash
git add VERSION_MANIFEST.json \
        mecris-go-project/app/build.gradle.kts \
        boris-fiona-walker/spin.toml \
        mecris-go-spin/sync-service/spin.toml \
        pyproject.toml \
        web/package.json \
        ROADMAP.md
git commit -m "chore: bump version to 0.0.1-rc.2"
git push origin main
```

### 4. Tag and Push Release

**Critical: Use `v` prefix**

```bash
git tag v0.0.1-rc.2
git push origin v0.0.1-rc.2
```

### 5. Monitor Release Workflow

The GitHub Actions Release workflow will:
1. Build Android APK (`mecris-go-project`)
2. Build WASM components (sync-service, boris-fiona-walker, etc.)
3. Publish GitHub Release with artifacts

Watch progress:
```bash
gh run watch --repo kingdonb/mecris
```

### 6. Verify Release

Check: https://github.com/kingdonb/mecris/releases/tag/v0.0.1-rc.2

Assets should include:
- `mecris-go-release-unsigned.apk`
- `wasm-components.tar.gz`

---

## Common Mistakes to Avoid

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| Tag `0.0.1-rc.2` (no `v`) | Release works but inconsistent with history | Delete tag, retag with `v` prefix |
| Skip `make bump-version` | Version strings out of sync | Always use the script |
| Push tag before committing version bump | Release built with old version | Commit first, then tag |
| Forget to run tests | Broken release | `make test` must pass |

---

## Rollback if Needed

If a release is pushed with wrong version:

```bash
# Delete release (auto-deletes tag) or:
gh release delete v0.0.1-rc.2 --yes
git tag -d v0.0.1-rc.2
git push origin :refs/tags/v0.0.1-rc.2

# Fix version, recommit, retag
make bump-version VERSION=0.0.1-rc.3
git commit -am "chore: bump version to 0.0.1-rc.3"
git push origin main
git tag v0.0.1-rc.3
git push origin v0.0.1-rc.3
```

---

## Files That Define Versions

| File | Component | Notes |
|------|-----------|-------|
| `VERSION_MANIFEST.json` | Master manifest | All components listed |
| `pyproject.toml` | Python package | `version = "..."` |
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