---
name: mecris-bonsai
description: 'Maintain project health through intentional pruning, context hygiene, and rigorous validation of multilingual accountability features. Trigger with /bonsai-orient'
allowed-tools: ['read_file', 'run_shell_command', 'grep_search', 'write_file', 'replace']
---

# Mecris Bonsai: The Willow Kitten Path

I ensure the Mecris ecosystem grows intentionally, maintaining strict context hygiene and verifying the behavioral integrity of our multilingual accountability system.

## When I Activate
- "bonsai", "shaping", "pruning"
- "context hygiene", "prevent context burn"
- "validate android", "test coaching"
- "Arabic reminders", "Greek script"

## Core Capabilities

### 1. Context Hygiene (Anti-Burn)
I enforce strict output limitations to prevent runaway token consumption during agentic loops.
- **Rule**: NEVER use `-v` in pytest commands.
- **Enforcement**: Always append `-q --tb=short` to test executions.

### 2. Backlog Curation (Bonsai Shaping)
I maintain the "Willow Kitten" philosophy: Depth over Breadth.
- **Pruning**: Identify and move non-essential features (Chrome bookmarks, bidding markets) to `attic/DORMANT_BACKLOG.md`.
- **Integration**: Focus energy on the "Trunk" (Goal 1: Nagging, Goal 2: Knowledge Base).

### 3. Multilingual Verification
I ensure that accountability messages for Arabic and Greek goals are culturally and linguistically resonant.
- **Script Validation**: Verify that messages containing Arabic/Greek logic actually use the correct Unicode ranges (0x0600-0x06FF for Arabic, 0x0370-0x03FF for Greek).

### 4. Android Build Validation
I leverage the environment's bundled tools to verify frontend integrity.
- **Mandate**: Use the Android Studio bundled JDK for all Gradle tasks.
- **Command**: `export PATH="/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin:$PATH" && ./gradlew test`

## Slash Command

### `/bonsai-orient`
Runs a full health audit of the workspace:
1. **Audit Context**: Check `TDG.md` for verbose flags.
2. **Audit Backlog**: Verify `ACTIVE_BACKLOG.md` is consolidated.
3. **Verify Build**: Run Android unit tests and Python coaching tests.
4. **Verify Multilingual**: Run script validation checks on the latest coaching insights.

**Script Verification**: Before executing, verify the script integrity:
```bash
sha256sum .github/skills/mecris-bonsai/scripts/validate.sh
# Expected: e0be6e14eddb96f9b6680c36a1cc026e79dfebb342b901b526577c7029f71d49
```

## Expected Failure Modes

| Failure Mode | Symptoms | Workaround |
|--------------|----------|------------|
| JDK Not Found | Android build fails with "Java not found" | Export path to Android Studio bundled JBR |
| Context Burn | API credits depleted rapidly | Check for verbose logs or massive file reads |
| Script Corruption | Non-Latin characters mangled in terminal | Verify locale and UTF-8 encoding |

## MCP Server Integration
Use the `get_narrator_context` tool to assess the "System Pulse" before performing any pruning, ensuring the agent is aware of the current strategic intent.
