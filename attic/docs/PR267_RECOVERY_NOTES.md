# PR #267 Recovery Notes: KAPT→KSP Migration Uncovered a Never-Compiled Branch

## TL;DR
The KAPT+Room "duplicate class" bug wasn't really a KAPT bug — it was hiding the fact that
**`compileDebugKotlin` had never once succeeded on this branch.** KAPT ran first in the task
graph and always failed, so the Kotlin compiler never got a chance to check the auth flow code.
Migrating to KSP unblocked the pipeline and exposed ~40 real compile errors underneath.

## What Was Actually Wrong

1. **`AuthErrorDatabase.kt`** — declared `open class` with an `abstract fun` (illegal Kotlin),
   plus a hand-rolled constructor calling `RoomDatabase(configuration)`, a constructor that
   doesn't exist. Rewrote as a standard `abstract class : RoomDatabase()`.

2. **`AuthState.kt` — didn't exist.** `MainActivity`, `AuthViewModel`, and
   `PocketIdAuthRepository` all referenced `com.mecris.go.auth.AuthState` (`Idle`, `Loading`,
   `Authenticated(token)`, `Error(message, isPermanent)`) extensively, but the file defining it
   was never committed. Reconstructed it from ~15 call sites across the three consumers.

3. **`AuthViewModel.kt`** — duplicate `companion object`, `import kotlinx.coroutines.pow`
   (doesn't exist, needed `kotlin.math.pow`), `delay(x, TimeUnit.MINUTES)` (delay doesn't take a
   `TimeUnit` overload), and a `when` branch comparing a parameterized data class bare instead
   of with `is`.

4. **`PocketIdAuthRepository.kt`** — several `const val`s declared at class-body scope (illegal,
   `const` requires top-level/object/companion), `EncryptedSharedPreferences.create(...)`
   assigned to a return type it doesn't return (real return type is `SharedPreferences`),
   `Instant.epochMilliseconds` (that's a `kotlinx.datetime` property; this file uses
   `java.time.Instant`, which has `.toEpochMilli()`), invalid reassignment of AppAuth's
   read-only `accessToken`/`accessTokenExpirationTime` (fixed via the real API,
   `setNeedsTokenRefresh(true)`), and references to `AuthorizationException.TYPE_NETWORK_ERROR` /
   `TYPE_HTTP_ERROR` / `.responseCode`, none of which exist in AppAuth 0.11.1 (verified against
   the actual sources jar). Simplified to reuse the existing message-based `AuthError.fromException`.

5. **`AuthError.kt`** — a top-level extension function referenced `AuthError`'s nested sealed
   subtypes (`TlsHandshakeFailed`, etc.) unqualified; only valid from *inside* the interface body,
   not from a top-level function. Added a proper `AuthError.detail` extension property and fixed
   the qualification. Also had the same `epochMilliseconds` vs `.toEpochMilliseconds()` mixup.

6. **Missing `material-icons-core` dependency** — `Icons.Filled.*` usage in `MainActivity.kt`
   was relying on a transitive dependency that isn't actually pulled in by `material3` at the
   Compose BOM version we moved to. Added it explicitly.

7. **`compileSdk`/`targetSdk` 35 → 37** — Compose BOM `2026.08.00` requires compiling against
   API 37.

8. **Stale test fixture** — `ReviewPumpCalculatorTest` still had the pre-fix assertion
   (`debt coverage ratio exceeds one when over-cleared`, expecting an uncapped `1.875`) from
   before this branch's last merge from `main`. Re-applied the same fix landed on `main` in #272
   (ratio is capped at `1.0` per spec, in both the Kotlin and Python implementations).

## What This Means
None of the above are KSP/version-migration problems — they're pre-existing bugs in the auth
flow feature that KAPT's failure had been silently masking from CI and from local builds alike.
The KSP migration itself (Kotlin 2.2.21, KSP 2.2.21-2.0.5, Room 2.8.4, AGP 9.3.1, Gradle 9.7.0,
Compose BOM 2026.08.00) worked on the first real attempt once these were fixed.

## Current State
- `./gradlew clean kspDebugKotlin compileDebugKotlin` — **BUILD SUCCESSFUL**
- `./gradlew testDebugUnitTest` — **BUILD SUCCESSFUL**, all unit tests pass
