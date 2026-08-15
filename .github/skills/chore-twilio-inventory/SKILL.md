---
name: chore-twilio-inventory
description: 'Weekend chore 5-minute survey and verification for Twilio WhatsApp messaging, Meta Utility templates, 24-hour session window rules, and notification delivery. Trigger with /chore-twilio-inventory'
allowed-tools: ['run_command', 'view_file', 'grep_search', 'list_dir', 'call_mcp_tool']
---

# Weekend Chore: Twilio & WhatsApp Template Inventory

Part of the **Weekend Chores** accountability workflow. This skill guides the **human operator** and AI assistant through a 5-minute inspection of the Twilio messaging pipeline, WhatsApp Meta template approvals, and outbound notification routing.

## The Twilio & WhatsApp Realities

- **Operating Cost**: ~$2–$3/month to maintain the dedicated phone number.
- **SMS Status (A2P 10DLC)**: Regular SMS is **disabled**. Without an approved A2P 10DLC campaign, carrier filtering will block messages and incur failed delivery fees. All mobile notifications route via **WhatsApp**.
- **WhatsApp 24-Hour Rule**:
  - **In-Session (24h Window)**: If you sent a message to the bot within the last 24 hours, freeform text messages can be sent.
  - **Out-of-Session (Proactive Nags)**: Outside the 24h window, **all messages must use pre-approved Meta WhatsApp Templates**.
- **Meta Template Constraints (Utility Category)**:
  - Templates must be registered as **UTILITY** (account alerts, critical maintenance, deadline/derailment warnings).
  - Variable substitution is strictly bound to positional parameters (`{{1}}`, `{{2}}`, `{{3}}`).

---

## Approved Template Catalog (`data/approved_templates.json`)

| Content SID | Template Name | Category | Primary Use Case |
|---|---|---|---|
| `HXdf745ded3d0f6373f3333765ba18fd07` | `mecris_system_maintenance_v2` | UTILITY | System pulse, failover alerts, sync issues |
| `HXf39921201717621e5bac94a4e6d4eab3` | `mecris_daily_briefing_v2` | UTILITY | Morning summary & accountability roadmap |
| `HX62f7e3269007f950cfde304f2a290b6d` | `mecris_sync_confirmation_v2` | UTILITY | Health Connect / Clozemaster sync receipts |
| `HX1aa68d63582981d8dee93596760334cf` | `mecris_budget_statement_v2` | UTILITY | LLM spend warnings & Virtual Budget thresholds |
| `HX9403f1b85350b8c05780a1128b79f3c2` | `mecris_status_v2` | UTILITY | Goal safebuf snapshot & derailment prevention |
| `HXf7661d0e55ad51e926e2bddb3c7c66ce` | `mecris_milestone_notice_v1` | UTILITY | Majesty Cake & review pump clearance celebrations |
| `HXecc09b4995719ceb65dfb6da544343cc` | `mecris_preference_update_v1` | UTILITY | Vacation mode & notification window changes |
| `HX138b3d037c5ebcb6a828d85ad8e9f3a8` | `mecris_security_checkpoint_v1` | UTILITY | PocketID token expiry & perimeter reminders |
| `HX97c5978812394a2daf5fefca76078934` | `mecris_activity_verification_v1` | UTILITY | Physical walk reminders for Boris & Fiona |
| `HX638b7f9403e04c8fa880370f1b7a9ba1` | `mecris_urgency_alert_v2` | UTILITY | Tier 2 emergency escalation (Arabic reviewstack) |
| `HXbb3327078f3e3361dad21f0a2dc6a8dd` | `mecris_daily_alert_v1` | UTILITY | General daily accountability trigger |

---

## 5-Minute Guided Chore Routine

### Step 1: Check Local Delivery Mode & Environment
```bash
# Check if delivery method is set to whatsapp vs console
grep -E "REMINDER_DELIVERY_METHOD|TWILIO_" .env || echo "REMINDER_DELIVERY_METHOD defaults to console if unset"
```

### Step 2: Sync & Validate Approved Templates from Twilio
```bash
.venv/bin/python whatsapp_template_manager.py
```
- Fetches active approval statuses from Meta/Twilio and updates `data/approved_templates.json`.

### Step 3: Run Nag Evaluation Test (Dry Run)
```bash
.venv/bin/python -m cli.main nag eval
```
- Confirms the nag engine correctly matches the urgent trigger to an approved `template_sid` (e.g., `HX638b7f9403e04c8fa880370f1b7a9ba1`) and structured positional variables.

### Step 4: Human Visual Confirmation (The Chore)
1. Check your phone's WhatsApp chat with the Mecris bot.
2. If no messages have been received recently, send a test ping to the bot to open the 24-hour conversational window.
3. Review whether `REMINDER_DELIVERY_METHOD=whatsapp` should be enabled in your local `.env` or if Akamai Functions handles the cloud cron schedule.
