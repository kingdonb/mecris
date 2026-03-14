# Mecris-Go: Android App Design & Architecture

> **Mecris-Go**  
> *Automated fitness inference, low-friction accountability, and proactive verification*

## 1. Narrative & Strategic Goal

Mecris-Go (formerly Mecris Mobile) serves as the "pulse" and "sensory input" of the personal accountability system. The primary goal has shifted from a simple notification hub to a **proactive inference engine** using local health data. 

Instead of relying on the user to manually log Beeminder points or inform the system that a walk occurred, Mecris-Go automatically pulls activity data from the phone, infers whether a walk happened, proactively reaches out to confirm or encourage, and directly creates the Beeminder data points.

## 2. Core Technical Flow: Health Connect & Inference

*Note: The Google Fit API is deprecated and shutting down. Mecris-Go will rely on the modern **Android Health Connect API** to read step, distance, and exercise route (GPS) data.*

### The Inference Pipeline
1. **Authorization**: User logs in (Google OAuth) and grants Mecris-Go read-access to Health Connect (Steps, Distance, Exercise Routes).
2. **Data Sync**: The app periodically polls Health Connect for new "Walking" sessions, distance covered, and GPS breadcrumbs.
3. **Inference Engine**: 
    - The backend (or on-device worker) analyzes the aggregated data.
    - *Example*: A cluster of 3,000 steps over 30 minutes with GPS data showing a path around the neighborhood.
    - *Conclusion*: "Dog Walk Detected."
4. **Proactive Communication**:
    - Mecris reaches out via Push Notification or SMS: *"I see you covered 1.5 miles this morning! Logged as a dog walk. Great job!"*
    - Alternatively, if the inference is ambiguous (e.g., lots of steps but strictly indoors): *"Lots of steps today! Did you take Boris and Fiona out, or were you just pacing?"*
5. **Beeminder Automation**: Once inferred (and/or confirmed via quick reply), Mecris-Go automatically dispatches the datapoint to Beeminder, eliminating manual data entry friction.
6. **Anti-Cheat & Verification (Future)**: 
    - Using the GPS Exercise Route data from Health Connect, Mecris-Go can verify that the walk actually happened outdoors, acting as a potential verification layer for Beeminder. 
    - It can also reconcile days where the phone was left behind if the user has a connected wearable, since Health Connect serves as a central hub for smartwatch data.

## 3. UI Interface Panels

### A. Onboarding & Health Connect Authorization
- **Goal**: Establish identity and secure local health data permissions.
- **UI Elements**:
    - Google OAuth Login.
    - Prominent permission prompt: "Connect to Health Connect" to read Steps, Distance, and Exercise Routes.

### B. The "Pulse" (Inference & Notification Hub)
- **Goal**: A chronological feed of Mecris inferences and communications.
- **UI Elements**:
    - Recent automated inferences (e.g., 📍 *Walk inferred at 10:30 AM*).
    - Quick-action buttons on inferences (e.g., "Confirm Dog Walk", "Not a dog walk", "Snooze").

### C. Compliance & Settings
- **Goal**: Manage A2P SMS consent, push notifications, and system toggles.
- **UI Elements**:
    - **A2P Consent Toggle**: Explicit opt-in for SMS fallback.
    - **Doggies Status Toggle**: "Doggies are away" (Boarding/Vacation mode) - changes the inference logic from "Dog Walk" to "Personal Activity".

### D. Goal Status Dashboard
- **Goal**: Real-time visibility into the system state.
- **UI Elements**:
    - **Daily Inferred Activity**: Live progress bar against step/distance thresholds.
    - **Beeminder Sync Status**: Shows when the last automated sync occurred based on health data.
    - **Budget & System Health**: Progress bars for Claude/Groq funds.

## 4. Technical Architecture

- **Frontend**: Jetpack Compose (Modern Android UI).
- **Health Data**: Android Health Connect SDK (requires Android 14+ natively, or available on Android 9-13 via app install).
- **Backend**: Spin app (Rust/Go) running on Fermyon Cloud or self-hosted, handling the heavy inference logic and Beeminder/SMS dispatch.
- **Communication**: REST API + FCM (Firebase Cloud Messaging).
- **Authentication**: Firebase Auth / Google Identity Services.

---
*Mecris-Go represents the transition from a passive dashboard to an active, sensory-aware accountability partner.*