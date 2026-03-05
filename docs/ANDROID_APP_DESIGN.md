# Android App Design Scaffold: Mecris Mobile

> **Mecris Mobile Extension**  
> *Low-friction accountability, push notifications, and consent management*

## 1. Narrative & Strategic Goal

Mecris Mobile serves as the "pulse" of the personal accountability system. While the backend (Spin/Serverless) handles the logic, the Android app provides:
- **Zero-Cost Notifications**: Push notifications via FCM (Firebase Cloud Messaging) as a primary alternative to SMS/WhatsApp.
- **Compliance Hub**: A central place to manage A2P SMS consent, opt-in/opt-out, and preference tuning.
- **Low-Friction Updates**: Quick buttons for common actions (e.g., "Walking Boris now") to update the system state without needing a terminal or voice-to-text.

## 2. Core UI Interface Panels

### A. Onboarding & Authentication
- **Goal**: Establish identity and connect to the Mecris backend.
- **UI Elements**:
    - Splash screen with the Mecris "Robot" branding.
    - Login via **Magic Link** (email) or **OAuth** (Google/GitHub).
    - "Welcome back" screen showing current goal summary (Narrator context snippet).

### B. Identity & Consent Dashboard (Compliance)
- **Goal**: Manage legal/compliance requirements for SMS and data.
- **UI Elements**:
    - **Phone Number Field**: Register the device for SMS fallback.
    - **A2P Consent Toggle**: Clear, explicit opt-in for SMS reminders (required for Twilio compliance).
    - **Message Preferences**: Checkboxes for "Walk Reminders", "Budget Alerts", "Beeminder Emergencies".
    - **Delete Account**: "Nuclear option" for user data rights.

### C. The "Pulse" (Notification Hub)
- **Goal**: A chronological feed of all Mecris communications.
- **UI Elements**:
    - List of recent alerts with icons (🚶‍♂️, 💰, 🚨).
    - "Read" vs. "Unread" states.
    - Quick-action buttons attached to notifications (e.g., "Snooze 1hr", "Done").

### D. Quiet Hours & Schedule
- **Goal**: Define when Mecris is allowed to be "sassy".
- **UI Elements**:
    - Time-range picker (e.g., "Don't bug me before 8 AM or after 9 PM").
    - Weekend toggle (Different schedule for Saturdays/Sundays).

### E. Goal Status Dashboard
- **Goal**: Real-time visibility into the system state.
- **UI Elements**:
    - **Dog Walk Progress**: "Boris & Fiona: ❌ Needed" or "✅ Logged".
    - **Budget Health**: Progress bar showing remaining Claude/Groq funds.
    - **Beeminder Risk**: List of goals with runway colors (Green/Yellow/Red).

## 3. New Functionality Enabled

1. **Rich Push Notifications**: Unlike SMS, Android push can include images, action buttons, and progress bars.
2. **Foreground Service/Live Activity**: Keep the "Dog Walk" status visible on the lock screen until it's completed.
3. **Location-Aware Reminders (Future)**: Detect when the user is at the park or out for a walk and automatically update the "Bike" goal status.
4. **Offline Mode**: Cache the last known status so you can check your goals even without a data connection.

## 4. Technical Architecture (Android + Spin)

- **Frontend**: Jetpack Compose (Modern Android UI).
- **Backend**: Spin app (Rust/Go) running on a serverless platform (e.g., Fermyon Cloud or self-hosted).
- **Communication**: REST API + FCM (Push).
- **Storage**: Mecris SQLite (via the Spin backend API).

---
*This document serves as the design scaffold for the Mecris Android application implementation.*
