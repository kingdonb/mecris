---
name: release-workflow
description: 'Standard procedure for creating, validating, bumping, and publishing Mecris ecosystem releases following docs/RELEASE_PROCESS.md. Trigger with /release-workflow'
allowed-tools: ['run_command', 'view_file', 'grep_search', 'list_dir', 'call_mcp_tool']
---

# Release Workflow: Mecris Ecosystem Release Procedure

Guides the AI assistant and operator through the standardized release procedure defined in [`docs/RELEASE_PROCESS.md`](file:///Users/yebyen/w/mecris/docs/RELEASE_PROCESS.md).

## Critical Version Tagging Convention

> **All release tags MUST use the `v` prefix:** `v0.0.1-rc.5`, `v0.0.1-beta.10`, `v0.0.1`, etc.

The GitHub Actions Release workflow triggers exclusively on tags matching `v*` and `0.*`. Always prefix with `v` to ensure consistent GitHub Release creation and tag history matching.

---

## 5-Step Release Execution

### Step 1: Pre-Release Validation (All Tests Must Pass)
```bash
make test-python
make test-rust
```

### Step 2: Create Release Branch & Bump Version
```bash
git checkout main && git pull origin main
git checkout -b release/v{VERSION}
make bump-version VERSION={VERSION} VC={VERSION_CODE}
```
*Note: Never manually edit version strings. `make bump-version` synchronizes 15+ references across Android, Spin, Web, Python, and manifests.*

### Step 3: Commit, Push & Open Pull Request
```bash
git add VERSION_MANIFEST.json mecris-go-project/app/build.gradle.kts boris-fiona-walker/spin.toml mecris-go-spin/sync-service/spin.toml pyproject.toml uv.lock web/package.json ROADMAP.md
git commit -m "chore(release): bump version to {VERSION} + VC={VERSION_CODE}"
git push origin release/v{VERSION}
gh pr create --title "chore(release): release v{VERSION}" --body "Release preparation for v{VERSION} (VC={VERSION_CODE})." --base main
```

### Step 4: Verify CI & Merge PR to Main
- Wait for mandatory CI checks on the PR to pass (`gh pr checks {PR_NUMBER}`).
- Merge PR cleanly to `main` via squash or merge commit.

### Step 5: Tag and Push Release on Main (Wait for Main CI First!)
```bash
git checkout main
git pull origin main

# Verify CI on main is 100% green before tagging:
gh run list --branch main -L 1

# Create and push the release tag with 'v' prefix:
git tag v{VERSION}
git push origin v{VERSION}
```
- GitHub Actions (`release.yml`) will build release artifacts, upload packages, and draft/publish the GitHub Release.
