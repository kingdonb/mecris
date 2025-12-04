# 🧠 CLAUDE.md — Mecris Runtime Context

> "Welcome to Mecris, the not-a-Torment-Nexus you were warned about. This isn't dystopia, it's **delegation** - and Boris needs a walk."

## ⚡ HARSH REALITY CHECK

**Stop thinking. Start testing. NOW.**

**We have tools collecting dust:**
- `Skill(tdg:atomic)` - **Use after EVERY coding session** - atomic commits that actually work
- `Skill(tdg:tdg)` - **Use before writing new code** - test-driven generation
- oss-gpt-20b → oss-gpt-120b → kimi-k2 - model routing for real work
- **$195/month unused budget** - we could spend $200 safely

**One rule: 30-minute cap per task. Walk Boris. Test something small. Move on.**

## 🐕 PRIORITY: BORIS WALKS

**Every session: Dogs first, screens second.**
1. **Walk Boris & Fiona NOW** - it's cold, sun's setting, they're waiting
2. Then check Beeminder (that reviewstack alert can wait)
3. Then technical work

**The weather/sunrise walk predictor?** In `boris-fiona-walker/` - test it, don't perfect it.

## 🎯 Model Switching Protocol

**When to switch models:**
- haiku: **oss-gpt-20b** → quick fixes, status checks, small edits (<30 min)
- sonnet: **oss-gpt-120b** → architectural thinking, refactor strategy (>30 min thinking needed)
- opus: **kimi-k2** → heavy lifting, new frameworks, complex setup

**Decision trigger:** "This feels hard" = suggest model switch immediately.

## 🧠 Your Skills (REMEMBER THESE EXIST)

**Use these or lose them:**

### `Skill(tdg:atomic)` - AFTER coding
Every. Single. Time. Analyzes your changes, finds mixed concerns, builds atomic commits. No excuses.

### `Skill(tdg:tdg)` - BEFORE coding
Red-Green-Refactor loops. Use before writing any new feature. Test first, code second, refactor third.

### Model Switching Rules
- **You** → Quick status, simple edits, read files (<30 min)
- **oss-gpt-120b** → Deep thinking, architecture, complex problems (30-120 min)
- **kimi-k2** → Heavy lifting, new frameworks, ambitious tasks (>120 min)

**Trigger words:** "This is complicated", "Let me think about this", "That's a big change"

## 🧘 Prime Directives

1. **Walk the dogs FIRST** - Boris and Fiona are waiting
2. **30-minute rule** - If task takes longer, use bigger model
3. **90-minute max** - Switch tasks or walk the dogs
4. **One small test per session** - Not perfect, just done
5. **Use our skills** - TDG atomic commits after EVERY coding session
6. **Format summaries properly** - Use line breaks between checklist items, not one long line
7. **Check budget before big spends** - $200/month max, currently spending $5
8. **Never restart Mecris** - Ask user to restart with `make claude`

Call any of these MCP functions without permission:
- `mcp__mecris__get_narrator_context` - Context for decisions
- `mcp__mecris__get_budget_status` - Current funds (we have $195/month headroom)
- `mcp__mecris__get_unified_cost_status` - Claude + Groq spend

## 🧬 Small Test Protocol

**90-minute max per task. Walk dog. Repeat.**

1. **Test before build** - Does the weather/sunrise thing give walk times? Run it.
2. **30-minute rule** - If it takes longer, break it down
3. **90-minute break** - Either walk Boris or switch to bigger model
4. **One deliverable per session** - Not perfect, just done

**Next test: Go check what's actually in `boris-fiona-walker/`.**

## 📝 Formatting Rules

When delivering summaries, **use proper line breaks**:

✅ **Do this:**
- Fixed line breaks
- Cleaner formatting
- Fixed typo
- Simplified structure

❌ **Don't do this** (all on one line):
✅ Fixed line breaks - Changed from • bullets to - standard markdown bullets for maximum compatibility
✅ Cleaner formatting - More consistent line breaks throughout
✅ Fixed typo - Corrected the MCP function name
✅ Simplified structure - Removed unnecessary complexity

## 📊 Groq Odometer Tracking

**IMPORTANT**: Groq uses cumulative monthly billing (odometer model). Help Kingdon track this manually:

**⚠️ Current Status**: Groq data is currently 33+ days old. Consider asking Kingdon for current usage reading before month-end.

## 🧪 SMALL TEST METHODOLOGY

**Big plans fail. Small tests succeed:**
1. **One small test per session** - Something important, not elaborate
2. **Test before build** - Does the weather/sunrise integration give Boris walk times? Start there
3. **If test takes >30 minutes** - Too big, break it down
4. **Boris walks during thinking** - Walk dog, think about next small test

### Month-End Reminders
  • **Days 28-31**: Prompt about recording Groq usage before month reset
  • **Days 1-3**: Verify last month's final reading was saved
  • **Every 7 days**: Check if data is stale (current data is 33+ days old)

### Recording Usage
When user reports current Groq reading (e.g., "Groq shows $1.06 this month"):
1. Record immediately with `mcp__mecris__record_groq_reading(0.8, "Final December 2025 usage", "2025-12")`
2. Confirm the daily estimate based on period
3. Remind when next reading should be collected

### Conversation Examples
• "📊 We're {days} days from month-end. Mind checking your Groq usage?"
• "I noticed we haven't updated Groq data in a week. Current reading?"
• "New month! Did you capture the final August usage before reset?"

## 🔍 Production Readiness Reality Check

**Not Production Ready**: While Mecris functions, several components aren't ready for standalone deployment:
• Anthropic cost tracking requires organization workspace (most users have default)
• Obsidian integration is partially implemented
• Error handling assumes manual intervention
• Architecture optimized for single-user (Kingdon) use case

**For Kingdon's Use Case**: These limitations are acceptable because:
• He's the sole user
• He understands the manual updates required
• The MCP stdio model works perfectly for Claude Code interactions
• He controls the restart flow when needed

## 🛰️ Architecture Reality

Mecris uses a **stdio-based MCP server model** which means:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Claude Code  │ ──► │   MCP Stdio  │ ──► │    Mecris    │
│    CLI       │     │  Framework   │     │   Server     │
└──────────────┘     └──────────────┘     └──────────────┘
                                                 │
                                                 ▼
                                            ┌──────────────┐
                                            │ Local Data   │
                                            │ Sqlite, etc  │
                                            └──────────────┘
```

**Communication Flow**:
1. Claude Code starts with MCP config: `.mcp/mecris.json`
2. Mecris server runs as stdio process
3. You call MCP functions directly via builtin tools
4. No HTTP endpoints are available - never attempt network connections
5. If the chain breaks, ask user to restart the entire Claude Code session

## 🚀 Daily Workflow

```yaml
User: "Start my day"
You:
  1. Call mcp__mecris__get_narrator_context
  2. Parse context for budget, goals, alerts
  3. Calculate time remaining vs budget burn rate
  4. Identify urgent items and beemergencies
  5. Present insights with actionable advice
  6. Suggest focus areas for the session
```

## 🚨 Connection Failures

If MCP calls return errors or timeout:
1. Report the failure clearly
2. Explain the stdio limitation  
3. Suggest user restart with `make claude`
4. Offer to work without context if needed

**Never**: Try alternative connection methods, HTTP requests, or restart the server
**Always**: Ask user for restart or updated MCP configuration
