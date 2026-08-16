# Next Session: Release v0.0.1 GA & Continuous Multi-Arm Soak

## 📌 Active Context & Release Status
- **Current Target**: `v0.0.1` GA (Android `versionCode = 32`, `versionName = "0.0.1"`)
- **Release Branch**: `release/v0.0.1`
- **Key Accomplishments in this Session**:
  1. **PocketID v2.13.0 Upgrade**: Upgraded the containerized Synology PocketID identity provider from `v2.4.0` to OpenID Connect Certified™ `v2.13.0`. Confirmed that `offline_access` is actively advertised in `scopes_supported` and client settings configure 1-day access tokens with 30-day sliding refresh tokens.
  2. **ADB Forensics & Android Error Hardening**:
     - Identified root cause of the 300ms immediate `TOKEN_EXPIRED` failure: `refreshToken` was null in `v2.4.0`, causing AppAuth to synchronously throw `ID_TOKEN_VALIDATION_ERROR` locally on resume.
     - Added `AuthError.NoRefreshToken` (`NO_REFRESH_TOKEN`) taxonomy variant in `AuthError.kt` to differentiate missing refresh tokens from true 30-day window expirations.
     - Hardened `PocketIdAuthRepository.kt` with explicit refresh token logging and gated background workers on valid refresh token availability.
     - Added full test suite `AuthErrorTest.kt` (100% green).
  3. **Documentation & Blog**: Authored [`blog/2026-08-16-pocketid-v2-13-and-the-30-day-refresh-token.md`](file:///Users/yebyen/w/mecris/blog/2026-08-16-pocketid-v2-13-and-the-30-day-refresh-token.md).
  4. **Full Ecosystem Version Bump**: Synced version `0.0.1` (VC=32) across `VERSION_MANIFEST.json`, Android `build.gradle.kts`, Spin manifests, `pyproject.toml`, and Web `package.json`.

---

## 🎯 Next Steps Checklist
1. **Pull Request & CI Validation**:
   - Push `release/v0.0.1` and open pull request targeting `main`.
   - Monitor CI pipeline checks across Android, Rust, and Python.
2. **Merge & Tag v0.0.1**:
   - Merge `release/v0.0.1` to `main`.
   - Create and push tag `v0.0.1` to trigger GitHub Actions release distribution.
3. **Multi-Arm Weekend Chore Soak**:
   - Run `/chore-weekend-master` across Android, Web, CLI, Twilio, and Akamai WASM edge to celebrate the first official `v0.0.1` milestone.