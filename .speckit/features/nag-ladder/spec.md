# Feature Specification: The Nag Ladder (v1.0)
**Status:** DRAFT (Reverse-Engineered from Session Logs)
**Date:** 2026-04-05
**Feature ID:** SYS-002 (Nag Ladder & Behavioral Escalation)

## 1. Intent
The Nag Ladder is a multi-tier notification engine designed to prevent "notification fatigue" while ensuring that critical goals (especially those nearing derailment) receive the attention they require. It transitions from low-friction, templated reminders to high-urgency, freeform alerts.

## 2. The Tiers

### 2.1 Tier 1: Gentle Reminder (Status Quo)
*   **Trigger**: Goal enters a state where activity is recommended (e.g., walk needed, Arabic reviews overdue).
*   **Message**: Standard, templated text.
*   **Channel**: WhatsApp (Standard).
*   **Cooldown**: Standard (e.g., 4-12 hours depending on goal type).

### 2.2 Tier 2: Escalated Coaching (Idle-Time Trigger)
*   **Trigger**: A Tier 1 reminder was sent, but the user has remained idle (no activity recorded) for a defined window (default: 6 hours).
*   **Message**: Context-aware, escalated coaching copy (e.g., referencing "Boris & Fiona" for walks or the specific "ReviewStack" for Arabic).
*   **Behavior**: Disables `use_template` to allow for more personalized, urgent text.

### 2.3 Tier 3: High Urgency (Runway Trigger)
*   **Trigger**: Beeminder runway is critically low (default: < 2 hours).
*   **Message**: High-urgency, freeform alert.
*   **Exemption**: Tier 3 is exempt from standard sleep windows (it will fire at 3 AM if the user is about to derail).
*   **Channel**: WhatsApp (High Urgency). *Note: SMS was removed due to A2P 10DLC compliance blockers.*

## 3. Success Criteria
*   **SC-001**: System correctly identifies Tier 2 escalation based on `message_log` history.
*   **SC-002**: System correctly triggers Tier 3 based on runway hours, bypassing sleep windows.
*   **SC-003**: The "Nag Eval" CLI tool correctly reports the tier of any calculated reminder.

## 4. User Stories
*   **US-001**: As a user, I want gentle reminders early in the day so I'm not immediately overwhelmed.
*   **US-002**: As a user, if I ignore a reminder for 6 hours, I want a more pointed coaching message to nudge me back to action.
*   **US-003**: As a user, if I am within 2 hours of a derailment, I want a high-priority alert regardless of the time of day.
