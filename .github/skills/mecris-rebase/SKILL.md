---
name: Mecris Rebase
description: Safely resolves git conflicts and ensures successful pushes during autonomous sessions. Use when git pull --rebase fails.
---
# Mecris Rebase

Guided workflow for resolving git conflicts when upstream changes interfere with an autonomous push.

## Workflow

### 1. Diagnose Conflict
Identify which files are in "both modified" state.
```bash
git status
```

### 2. Surgical Resolution
For each conflicted file:
1.  **Analyze**: Use `read_file` or `grep` to see the conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`).
2.  **Cooperative Decision**:
    *   If the conflict is in **logs** or **documentation** (`session_log.md`, `NEXT_SESSION.md`), merge the information from both.
    *   If the conflict is in **core logic**, prefer the upstream changes (`theirs`) unless the bot's task specifically required a fix in that spot.
    *   Use `git checkout --ours <file>` or `git checkout --theirs <file>` for clean binary/full-file choices.
3.  **Edit**: Manually resolve markers if a merge is needed.
4.  **Stage**: `git add <file>`

### 3. Verify Integrity
**NEVER** continue a rebase without verifying the build and tests.
1.  **Build**: If Android code was touched, run `cd mecris-go-project && ./gradlew assembleDebug`.
2.  **Test**: Run `PYTHONPATH=. .venv/bin/pytest`.

### 4. Continue & Push
1.  **Continue**: `git rebase --continue` (or `git merge --continue`).
2.  **Verify History**: `git log --oneline -5`.
3.  **Push**: `git push origin main`.

## Guidelines
*   **Don't give up**: If a rebase fails, you have plenty of turns to resolve it.
*   **Stay Atomic**: Keep the commit history clean.
*   **Document**: Add a note to the `session_log.md` about the conflict resolution.

## Activation
Use when: "push failed", "git conflict", "rebase failed", "diverged branches".

## Closing
"Conflict resolved and changes pushed to main. History is now synchronized."
