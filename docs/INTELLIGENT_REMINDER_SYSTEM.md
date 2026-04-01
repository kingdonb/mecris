# INTELLIGENT_REMINDER_SYSTEM.md

**Adaptive Daily Reminder System with Graceful Budget Degradation**  
*Updated: 2026-04-01 — Nag Ladder Implementation*

## 🎯 VISION

**Core Principle**: Reminders should be persistent but respectful. The "Nag Ladder" ensures that critical goals get increasing attention while respecting the user's focus through strict rate-limiting.

## 🏗️ NAG LADDER ARCHITECTURE

The system follows a three-tier escalation strategy based on urgency and user responsiveness.

### Global Rate Limit (Mandatory)
- **Limit**: No more than **2 messages per hour** across ALL channels.
- **Aggregate Cooldown**: A strict 30-minute quiet period is enforced after any message is sent, regardless of the reminder type or tier.

### Three-Tier Escalation

| Tier | Type | Trigger | Channel |
| :--- | :--- | :--- | :--- |
| **Tier 1** | Standard | Goal is CRITICAL or Walk needed | WhatsApp Template |
| **Tier 2** | Escalated | Idle for >6 hours OR specific escalation (e.g., Arabic) | WhatsApp Freeform |
| **Tier 3** | High Urgency | Runway < 2 hours (explicit "hours" unit) | WhatsApp High Urgency |

---

## 🔧 IMPLEMENTATION DETAILS

### Tier 1: Standard Reminders
Uses pre-approved WhatsApp templates (e.g., `urgency_alert_v2`, `mecris_activity_check_v2`). These are gentle, structured nudges.

### Tier 2: Idle-Time Escalation
If a Tier 1 reminder was sent more than 6 hours ago and the goal is still critical, the system promotes the next reminder to Tier 2.
- **Channel**: WhatsApp Freeform (bypasses templates for more direct language).
- **Mechanism**: `ReminderService._apply_tier2_escalation()` uses the message log to detect idle time.

### Tier 3: High Urgency (The "Final Countdown")
Fires when a goal's runway is expressed in hours (e.g., "1.5 hours") and is less than 2.0.
- **Channel**: WhatsApp Freeform with triple-siren (`🚨🚨🚨`) prefix.
- **Constraint**: Only fires for explicit "hours" strings. "0 days" stays at Tier 1/2 to distinguish between "due today" and "derailing now."

---

## 📱 MESSAGE EXAMPLES

**Tier 1 (Walk)**:
`[Template] Daily Walk: Pending. Boris & Fiona: Expectant.`

**Tier 2 (Escalated Arabic)**:
`🚨🚨 Arabic IGNORED 4x — OPEN CLOZEMASTER NOW. No excuses.`

**Tier 3 (Urgent)**:
`🚨🚨🚨 CRITICAL EMERGENCY: Weight Goal derails in under 2 hours — TAKE ACTION NOW.`

---

## 🎭 DESIGN PHILOSOPHY

**"Nag Until Done, But Never Spam"**

The system is designed to be annoying enough to drive action but disciplined enough to avoid being "noise." 
1. **Persistence**: It will continue to nag as long as the condition (CRITICAL goal) persists.
2. **Escalation**: The "shouting" gets louder (Tier 1 → 2 → 3) as time passes or the deadline nears.
3. **Respect**: The 2x/hour global limit ensures the bot can never "doom loop" or flood the user's notifications.

*Note: SMS delivery is explicitly DISABLED due to A2P registration requirements. All escalations happen via WhatsApp.*
