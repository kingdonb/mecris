---
name: chore-weekend-master
description: 'Master 5-minute weekend chore orchestrator for Mecris. Guides the human operator through Saturday & Sunday inventory passes across Web, Android, CLI, and Twilio, and conducts Sunday lookback flair verification. Trigger with /chore-weekend-master'
allowed-tools: ['run_command', 'view_file', 'grep_search', 'list_dir', 'call_mcp_tool']
---

# Master Weekend Chore: 5-Minute Accountability Loop & Flair

The master orchestrator for the **Mecris Weekend Chores** protocol. 

## The Weekend Chores Contract

1. **Duration**: Exactly 5 minutes of focused inventory and guided inspection.
2. **Frequency**: Must be executed **both days** of the weekend (Saturday and Sunday) to count as completed.
3. **The Sunday Lookback & Flair**:
   - On the Sunday chore run, the agent inspects the previous session logs and commit history to verify that Saturday's chores were done.
   - If both days pass, a commemorative **Chore Flair badge** is generated in the session log to record a continuous streak of clean, maintained infrastructure.
4. **Human-in-the-Loop**: The human visually confirms each arm (Web UI, Android client, CLI pulse, WhatsApp chat), while the AI assists with live builds, diagnostic queries, and log inspections.

---

## The 4-Arm Inventory Checklist

| Arm | Chore Skill | Human Action |
|---|---|---|
| **1. Web Frontend** | [`/chore-web-inventory`](file:///Users/yebyen/w/mecris/.github/skills/chore-web-inventory/SKILL.md) | Open `http://localhost:5173/`, connect to Neural Link via PocketID, and inspect System Pulse & Majesty Cake score (`0/3` vs `3/3`). |
| **2. Android Client** | [`/chore-android-inventory`](file:///Users/yebyen/w/mecris/.github/skills/chore-android-inventory/SKILL.md) | Launch Mecris Go on phone, confirm daily step count and 30-day Health Connect sessions, verify home Wi-Fi check-in. |
| **3. Mecris CLI** | [`/chore-cli-inventory`](file:///Users/yebyen/w/mecris/.github/skills/chore-cli-inventory/SKILL.md) | Run `.venv/bin/python -m cli.main pulse` to review the high-density terminal dashboard and goal runways. |
| **4. Twilio / WhatsApp** | [`/chore-twilio-inventory`](file:///Users/yebyen/w/mecris/.github/skills/chore-twilio-inventory/SKILL.md) | Verify WhatsApp connectivity, check Meta Utility template approvals (`HX...`), and open the 24h conversational window if needed. |

---

## Sunday Lookback & Flair Generation

On Sunday, if Saturday's chore was logged and Sunday's 4 arms are verified green, output the flair:

```text
╔════════════════════════════════════════════════════════════════╗
║             ✨ MECRIS WEEKEND CHORES COMPLETED ✨              ║
║                                                                ║
║  📅 Week of: {DATE}                                            ║
║  ✅ Saturday Pass: COMPLETE (Web + Android + CLI + Twilio)     ║
║  ✅ Sunday Pass:   COMPLETE (Web + Android + CLI + Twilio)     ║
║  🌟 Status:        CONTINUOUS STREAK VERIFIED                  ║
║  🍰 Momentum:      SYSTEM HARMONY & FULL ARM DISCOVERY         ║
╚════════════════════════════════════════════════════════════════╝
```
