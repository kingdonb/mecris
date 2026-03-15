# TDG Configuration (Mecris-Go Android)

## Project Information
- Language: Kotlin
- Framework: Android (Jetpack Compose)
- Test Framework: JUnit 4, MockK, Robolectric

## Environment Setup
export PATH="/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin:$PATH"

## Mandatory Pre-Commit Workflow
1. Build check: `./gradlew assembleDebug`
2. Test check: `./gradlew test`

## Build Command
./gradlew assembleDebug

## Test Command
./gradlew test

## Single Test Command
./gradlew testDebugUnitTest --tests "<test_class>.<test_name>"

## Coverage Command
./gradlew koverHtmlReport

## Test File Patterns
- Test directory: app/src/test/java/
