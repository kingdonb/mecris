# macOS `gsed` workaround for Claude Code CLI

**Issue**: Users encounter a runtime error when running Claude Code on macOS (and Linux) with Node.js v25. The error originates from a `sed` command that expects GNU‑sed syntax, but macOS ships with BSD‑sed which does not understand the options used by Claude Code.

**Reference**: GitHub issue [#9795](https://github.com/anthropics/claude-code/issues/9795) – comment #3417734369 describes the fix.

## Fix steps
1. **Install GNU‑sed** via Homebrew:
   ```bash
   brew install gnu-sed
   ```
2. **Use `gsed` instead of the built‑in `sed`** when following the instructions or running the CLI. For example, replace:
   ```bash
   sed -i '' "s/.../.../" file.txt
   ```
   with:
   ```bash
   gsed -i "s/.../.../" file.txt
   ```
   (Note: the `-i` flag works without the empty string argument on GNU‑sed.)

## Why this works
- Homebrew’s `gnu-sed` binary is installed as `gsed` to avoid clobbering the system `sed`.
- `gsed` provides the GNU extensions (`-i` with optional backup suffix, extended regex support, etc.) that Claude Code’s scripts rely on.

## Recommendations for Mecris users
- Add `brew install gnu-sed` to your setup script or onboarding guide.
- Alias `sed` to `gsed` in your shell profile if you prefer the original command name:
  ```bash
  echo 'alias sed="gsed"' >> ~/.zshrc   # or ~/.bash_profile
  source ~/.zshrc
  ```
- Verify the correct version:
  ```bash
  gsed --version   # should show GNU sed 4.x
  ```

## Future outlook
The Claude Code team is aware of the incompatibility and plans to bundle a cross‑platform solution or adjust scripts to be POSIX‑compatible. Until then, this `gsed` workaround restores full functionality on macOS.
