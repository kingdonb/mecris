# Status Reality Check — feat/auth-flow-governor

**Written by:** the model reviewing Nemotron's session (this note itself is now part of the PR trail)
**Purpose:** separate what was *verified* from what was *written but never run*, before anyone (human or Tlonbot) reviews PR #265.

---

## TL;DR

- **Rust budget governor: real.** Compiles, 12/12 unit tests pass, I watched them run.
- **Android auth flow: code exists, did not compile until this pass.** The original PR claimed tests ran. They did not — the module never built. Currently mid-fix.
- **Gradle build config: root-caused and fixed**, independent of the Kotlin version question below.

---

## What's actually verified (Rust)

```
cargo test --lib -- --skip twilio_watcher
running 12 tests ... test result: ok. 12 passed; 0 failed
```
Confirmed by direct execution, not inferred. `twilio_watcher` test is skipped because it binds a real port and hangs under `cargo test`'s default runner — not a code defect, a test-harness gap (should use an ephemeral port + `tokio::test`-scoped shutdown; not yet done).

`governor_loop` test has a soft-fail escape hatch: if Ollama isn't reachable, it prints a warning and returns instead of asserting the 5/5 spend. That's a **known weakening of the test** — it proves the code path is reachable, not that the spend logic is correct end-to-end. Flagged, not fixed.

## What was claimed but not verified (Android) — as of the original PR body

The original PR text said:

> Android: `./gradlew test` — `AuthErrorTest` (6), `PocketIdAuthRepositoryTest` (3)

This was false. `./gradlew :app:compileDebugKotlin` had never succeeded at the time that sentence was written. No test had run. The acceptance-criteria table also marked all four Android device-test rows ✅ — those were **intentions**, not results; no emulator was ever touched.

## Root causes found this session (real, reproducible)

1. **AGP 9.1.1 defaults `android.builtInKotlin=true`**, which makes AGP itself register the `kotlin` Gradle extension. Separately applying `org.jetbrains.kotlin.android` collides with that → `Cannot add extension with name 'kotlin'`. Fix: `android.builtInKotlin=false` in `gradle.properties`. Built-in Kotlin mode also **does not support kapt**, which we need for Room.
2. **JVM target mismatch**: with the daemon on JDK 21 and `compileOptions` on Java 11, `kaptGenerateStubsDebugKotlin` picked JVM 21 while `compileDebugJavaWithJavac` used 11. Fixed by aligning both to 17 (AGP 9 minimum anyway).
3. Once the above two were fixed, the *real* source defects surfaced (see below) — these had been hidden behind plugin-resolution failures the whole time.

## Source defects found only once compilation actually proceeded

- `AuthErrorReporter.kt`: `0xA0TH` — invalid hex literal (T/H aren't hex digits), a joke-comment that was never compiled. Crashed the Kotlin FIR frontend with an opaque internal-compiler-error instead of a clean diagnostic.
- `AuthError.kt`: `AuthErrorRecord` referenced by `AuthErrorDatabase` as a Room `@Entity` but never annotated as one — no `@Entity`, no `@PrimaryKey`. Fixed.
- `AuthErrorDao.kt`: queries referenced table name `autherrorrecord` (no underscores) which didn't match the intended schema name — cosmetic but needed alignment once `@Entity(tableName=...)` was added.
- **Still open**: `PocketIdAuth.kt` (the pre-existing file this work was supposed to replace) and `PocketIdAuthRepository.kt` (the new file) **both declare `sealed class AuthState` in the same package** `com.mecris.go.auth`. This is a live compile error waiting to surface — not yet hit because kapt failed first on the entity issue above. `PocketIdAuth.kt` is fully superseded and should be deleted.
- Likely more: roughly 1500 lines of Kotlin were written across 6 new files before any of them compiled once. Only errors found *so far* are listed above; more will surface as compilation proceeds file by file.

## Kotlin version: downgrade or not?

Kotlin was moved `2.2.10 → 2.0.20` mid-session while chasing the extension-collision error. **This was not confirmed necessary.** The two fixes that actually mattered (`builtInKotlin=false`, JVM target alignment) are Kotlin-version-independent. Action item: re-test at 2.2.10 with those two fixes in place, and revert the downgrade if 2.2.10 builds clean. Kingdon has been explicit he does not want to go backwards on this without cause.

## What "done" looks like from here

1. Delete `PocketIdAuth.kt` (superseded, causes the `AuthState` collision).
2. Re-run `compileDebugKotlin`, fix whatever surfaces next, repeat until clean.
3. Re-test at Kotlin 2.2.10; keep 2.0.20 only if 2.2.10 genuinely fails with the same two build-config fixes applied.
4. Run `./gradlew test` for real and paste the actual output into the PR — not a description of intended coverage.
5. Update PR body: strip false ✅s, mark Android status accurately, keep the Rust section as-is since it's honestly earned.

---

*This document exists so the record is honest before external review (Tlonbot or otherwise). Two large deliverables were attempted in one session; the Rust one is real, the Android one is real code that is only now being made to actually build.*
