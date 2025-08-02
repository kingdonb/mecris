# 📊 Narrator Context Architecture

> **How Mecris aggregates and synthesizes personal data for strategic decision-making**

## 🔄 Context Aggregation Flow

The narrator context system (`GET /narrator/context`) performs **real-time synthesis** of multiple data sources to provide strategic insights, not just raw data dumps.

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Obsidian      │    │    Beeminder     │    │  Narrator       │
│   Vault         │───▶│    Goals         │───▶│  Context        │
│                 │    │                  │    │  Synthesis      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
│ Goals Patterns  │    │ Emergency States │    │ Strategic       │
│ Todo Checkboxes │    │ Derail Risks     │    │ Recommendations │
│ Daily Notes     │    │ Progress Data    │    │ Urgent Actions  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

---

## 📝 Data Sources and Processing

### 1. Obsidian Goals Extraction

**Search Patterns** (obsidian_client.py:94-100):
```python
goal_patterns = [
    "## Goals",          # Section headers
    "# Goals", 
    "### Current Goals",
    "- [ ] Goal:",       # Checkbox goals
    "**Goal:**"          # Bold goals
]
```

**File Dependencies:**
- **No frontmatter required** - uses content-based pattern matching
- **No specific file structure** - searches across entire vault
- Supports multiple folder structures: `Daily Notes/`, `Journal/`, `daily/`, root level

**Goal Data Structure:**
```python
{
    "content": "Complete project X",
    "completed": True/False/None,
    "source_file": "Daily Notes/2025-07-30.md",
    "source_section": "## Goals",
    "line_number": 15,
    "last_updated": "2025-07-30T10:30:00"
}
```

### 2. Todo Extraction

**Search Method** (obsidian_client.py:168-170):
- Searches for `"- [ ]"` (incomplete) and `"- [x]"` (completed)
- **Excludes goal-like todos** containing "goal" keyword
- Extracts priority markers (`🔥`, `!!!`, `!!`, `!`)
- Identifies tags (`#tagname`)

**Todo Data Structure:**
```python
{
    "content": "Fix authentication bug #urgent",
    "completed": False,
    "indent_level": 0,
    "source_file": "projects/backend.md",
    "line_number": 42,
    "priority": "high",          # from 🔥 or !!!
    "tags": ["urgent"],          # from #urgent
    "last_updated": "2025-07-30T10:30:00"
}
```

### 3. Daily Notes Processing

**File Path Resolution** (obsidian_client.py:242-247):
```python
daily_note_patterns = [
    f"Daily Notes/{date}.md",    # Primary pattern
    f"{date}.md",                # Root level
    f"Journal/{date}.md",        # Journal folder
    f"daily/{date}.md"           # Lowercase daily folder
]
```

**Fallback:** If no exact path match, searches vault for date string and returns first matching file.

**❌ Current Limitation:** Daily notes are **NOT included** in narrator context aggregation - only retrieved via dedicated `/daily/{date}` endpoint.

### 4. Beeminder Integration

**Emergency Classification** (beeminder_client.py:137-146):
- `CRITICAL`: safebuf ≤ 0 (derailing now)
- `WARNING`: safebuf = 1 (derails tomorrow)  
- `CAUTION`: safebuf ≤ 3 (derails within 3 days)
- `SAFE`: safebuf > 3

---

## 🧠 Strategic Synthesis Logic

### Context Response Structure
```python
NarratorContextResponse {
    "summary": "Active goals: 5, Pending todos: 12, Beeminder goals: 8",
    "goals_status": {"total": 5, "sources": ["obsidian"]},
    "urgent_items": ["DERAILING: writing-goal", "DERAILING: exercise"],
    "beeminder_alerts": ["Derails tomorrow - act today", "Add 2.5 units"],
    "recommendations": ["Address critical Beeminder goals immediately"],
    "last_updated": "2025-07-30T10:30:00"
}
```

### Recommendation Engine (mcp_server.py:248-254)

**Automated Recommendations:**
- `> 10 pending todos` → "Consider prioritizing todos - large backlog detected"
- `Critical Beeminder goals` → "Address critical Beeminder goals immediately"  
- `No active goals` → "No active goals found - consider setting objectives"

---

## 🔍 What's Missing: Daily Notes Integration

### Current Gap
The narrator context **does not summarize recent daily notes** - this is a significant limitation for providing recent context about progress, mood, or decisions.

### Daily Notes Architecture (Not Yet Implemented)
**Potential Integration Points:**
1. **Recent Entries Summarization**: Last 3-7 days of daily notes
2. **Progress Tracking**: Changes in goals/todos over time
3. **Mood/Energy Indicators**: Extract energy levels, blockers, wins
4. **Decision Context**: Recent decisions or changes in direction

**File Dependencies for Daily Notes:**
- **No frontmatter required** - uses content parsing
- **Date-based file naming**: `YYYY-MM-DD.md` format
- **Flexible folder structure**: Multiple path patterns supported
- **Content structure**: Freeform markdown, no specific format required

---

## 🚨 Critical Architecture Insights

### 1. **No Frontmatter Dependencies**
- System uses **content-based pattern matching**, not YAML frontmatter
- Works with existing Obsidian vaults without restructuring
- Resilient to different organizational styles

### 2. **Real-Time Synthesis**
- Each context request performs **live aggregation** from all sources
- No caching - always current state
- High latency potential with large vaults

### 3. **Deduplication Logic**
- Goals: `content:source_file` key
- Todos: `content:source_file:line_number` key
- Prevents double-counting across multiple files

### 4. **Strategic Focus**
- **Not just data aggregation** - provides actionable insights
- **Risk-aware** - highlights critical states requiring immediate attention
- **Recommendation engine** - suggests specific actions based on patterns

### 5. **Missing Recent Context**
- ❌ No daily note summarization in narrator context
- ❌ No progress trend analysis
- ❌ No temporal awareness beyond Beeminder deadlines

---

## 🔧 Implementation Recommendations

### Priority 1: Daily Notes Integration
Add recent daily notes summarization to narrator context:
```python
# In get_narrator_context()
recent_notes = await get_recent_daily_notes(days=7)
context_summary = extract_recent_context(recent_notes)
```

### Priority 2: Context Caching
Implement intelligent caching to reduce latency:
- Cache vault searches for 5-10 minutes
- Invalidate on known file modifications
- Background refresh for critical data

### Priority 3: Temporal Awareness
Add progress tracking over time:
- Todo completion velocity
- Goal progress trends  
- Beeminder trajectory analysis

---

**The narrator context system is designed for strategic decision-making, not data dumps. It synthesizes multiple sources to provide actionable insights about what requires immediate attention and what's trending in the right direction.**