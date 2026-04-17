# Feature: Human-Centric "Sovereign-First" Notification Engine

## Problem Statement
The current Android notification system is rigid and occasionally misaligned with the user's daily reality. It lacks awareness of "Solar Windows" (telling you to walk after dark), "Personal Context" (nagging about doggies when they are boarded or missing), and "Execution Velocity" (sending notifications for tasks already completed during a delay). This results in a "nagging" experience that feels robotic rather than supportive, specifically manifesting in the "Moussaka in the morning" bug where late-day rewards are suggested during morning pressure hours.

## Solution
Implement a **Human-Centric Notification Engine** that is solar-aware, narrative-sensitive, and temporally fuzzy. The app will transition from a "Fixed Schedule" model to a "Two-Stage Fuzzy Pivot" model. It will respect the user's "Sovereign Location" for weather/solar checks without invasive tracking and will provide "Deep Intents" to move the user from "Reminded" to "Working" with one click.

## User Stories

1. **Randomized Delay (Fuzz)**: As a user, I want the app to wait a random amount of time (5-35 mins) after identifying a goal debt, so that the reminder feels less like a scheduled robot and more like an observant partner.
2. **Pre-Notification Verification**: As a user, I want the bot to re-verify my progress right before notifying me, so that if I did the work during the "fuzz delay," it doesn't nag me for a finished task.
3. **Smart Pivot**: As a user, I want the bot to "Pivot" to the next most important task if my original target is cleared, so that every notification is relevant.
4. **Narrative Sensitivity (Temporary)**: As a user, I want to set a "Vacation Mode Until" date, so that the narrative suppresses references to Boris & Fiona (doggie mode) and uses generic physical reminders during sensitive periods.
5. **Narrative Sensitivity (Permanent)**: As a user, I want to set a permanent "Vacation Mode," so that the app remains useful even if I do not currently have dogs.
6. **Solar Awareness**: As a user, I want the app to know when the sun is down at my location, so it stops nagging me to walk and instead suggests evening goals like Greek.
7. **Weather Oracle**: As a user, I want a "Weather Oracle" endpoint that provides detailed weather data (haze, temp, rain), so the bot can make intelligent remarks about current conditions.
8. **Location Sovereignty**: As a user, I want a Settings screen to manage my "Oracle Location" manually or via one-time GPS cache, with a "View on Maps" intent for transparency.
9. **Auth Resilience**: As a user, I want a Logout option and clear Re-auth redirections when the cloud token expires.
10. **Deep Intent Action**: As a user, I want notification buttons to deep-link directly into Clozemaster or Health Connect, so I can start working immediately.

## Success Criteria

- [ ] `WalkHeuristicsWorker` schedules `DelayedNagWorker` with a 5-35 minute random delay.
- [ ] `DelayedNagWorker` re-fetches status before showing a notification.
- [ ] Notifications for walks are suppressed after sunset.
- [ ] Narrative strings change based on `vacation_mode_until` DB flag.
- [ ] Settings UI allows manual location entry and Maps verification.
- [ ] Notification buttons successfully launch Clozemaster/Health Connect.

## Edge Cases

- **No Connectivity during Stage 2**: App falls back to local data and generic strings.
- **Goal cleared during delay**: App pivots to next goal or stays silent if all clear.
- **Multiple goals cleared**: App identifies next priority in hierarchy (Arabic -> Walk -> Greek).
- **Sunset occurs during delay**: App pivots from Walk to Greek.

## Out of Scope
- Direct OAuth credential collection via Android UI.
- Specific deep-linking into individual language categories in Clozemaster.
