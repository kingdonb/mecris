# The Weekend Chores Protocol & Rediscovering the Lost Arms of Mecris

**Date:** 2026-08-15  
**Author:** Antigravity (Gemini 3.7) & Kingdon  
**Topic:** Microservice Architecture, Human-in-the-Loop Accountabilities, and Weekend Chore Skills  

---

## 1. The Morning After the Release

Yesterday we shipped the latest pre-0.0.1 release of the Mecris Android client (`v0.0.1-rc.4`, versionCode 28). When we tested the authentication flow last night, things appeared to break. Yet this morning, without changing a line of code, the app was functioning smoothly again.

Reviewing the live ADB logs and tracing the architecture revealed the mystery:
- **The Perimeter Reality**: PocketID (`https://metnoom.urmanac.com`) runs on the home LAN behind a reverse proxy and firewall.
- **The Friday Night Bar Run**: When trying to refresh the access token outside the home network without an active VPN tunnel, AppAuth encountered network timeouts and placed a transient `AuthorizationException` on the internal state.
- **The Morning Recovery**: As soon as the device re-entered the home Wi-Fi perimeter, the `MecrisDashboard` surgical resume refresh fired, successfully refreshed the tokens, and cleared the transient error.

This sparked a bigger realization: **we are constantly rediscovering the project at the start of every session.** Mecris is a multi-modal bundle of microservices written in different languages (Python, Kotlin, TypeScript/React, Rust, Go), communicating over HTTP, FastMCP, SQLite/Neon Postgres, and WhatsApp.

To prevent architectural drift and forgotten components, we established the **Weekend Chores Protocol**.

---

## 2. The Weekend Chores Philosophy: Human-in-the-Loop

Weekend chores are not automated background tasks running silently in the dark. **They are designed for the human operator and the AI assistant to do together.**

```
               ╔═══════════════════════════════════════════╗
               ║         WEEKEND CHORES PROTOCOL           ║
               ║    5 Minutes • Saturday & Sunday Loop     ║
               ╚═══════════════════════════════════════════╝
                                     │
           ┌─────────────────────────┴─────────────────────────┐
           ▼                                                   ▼
┌─────────────────────────┐                         ┌─────────────────────────┐
│     SATURDAY PASS       │                         │       SUNDAY PASS       │
│  - Play-test & survey   │                         │  - Re-verify 4 arms     │
│  - Run builds & tests   │                         │  - Check Saturday log   │
│  - Zero ad-hoc mutation │                         │  - Award Weekly Flair ✨ │
└─────────────────────────┘                         └─────────────────────────┘
```

### Core Rules:
1. **Time-Capped**: Exactly 5 minutes per pass.
2. **Two-Day Cadence**: Must be completed both Saturday and Sunday to count as done.
3. **No Speculative Feature Hacking**: It is an inventory and diagnostic check. We build, test, probe, observe, and document learnings into skill documents without introducing ad-hoc code changes.
4. **Human Verification**: The agent spins up servers and runs unit suites, while the human visually interacts with the UI, logs in, checks their step count, and observes goal runway.
5. **The Sunday Lookback**: On the second run each week, the agent inspects the previous day's log and generates a retrospective **Weekend Chore Flair** badge.

---

## 3. Inventory of the 4 Core Arms

During our first Saturday chore pass, we formalized 4 dedicated `chore-*` skills:

### Arm 1: The Web Frontend (`/chore-web-inventory`)
- **Location**: [`web/`](file:///Users/yebyen/w/mecris/web)
- **Stack**: React 19 + TypeScript + Vite + `oidc-client-ts` / `react-oidc-context`.
- **Live Interface**: Served at `http://localhost:5173/`.
- **Key Features**:
  - **Neural Link Login**: PocketID PKCE authentication.
  - **System Pulse Matrix**: Live modality heartbeats (`MCP SERVER`, `AKAMAI FUNCTIONS`, `ANDROID CLIENT`).
  - **Momentum Visualizer**: Animates goal completion states up to the **3/3 Majesty Cake** (🍰).
  - **The Review Pump**: Interactive multiplier sliders for Arabic and Greek Clozemaster liabilities.
  - **Odometers**: Virtual Budget and Today's Distance (MI).
- **Graceful Failover**: Probes `Home` $\rightarrow$ `Akamai` $\rightarrow$ `Fermyon` to ensure transparent cloud degradation.

### Arm 2: The Android Client (`/chore-android-inventory`)
- **Location**: [`mecris-go-project/app/`](file:///Users/yebyen/w/mecris/mecris-go-project/app)
- **Stack**: Kotlin + Jetpack Compose + Health Connect API + WorkManager.
- **Diagnostics**: Tested via live Wi-Fi ADB logcat (`adb logcat -d -v time`).
- **Telemetry**: Local Health Connect caching (22 sessions in 30 days) operates completely offline; sync workers push walk inferences to Neon Postgres when connectivity to the backend API is restored.

### Arm 3: The Mecris CLI (`/chore-cli-inventory`)
- **Location**: [`cli/main.py`](file:///Users/yebyen/w/mecris/cli/main.py)
- **Stack**: Python 3.12 + Rich terminal formatting.
- **Interactive Tools**:
  - `mecris pulse`: High-density ecosystem status table showing goal runways, safebuf days, and urgent alerts.
  - `mecris presence check|take|release`: Mutual-exclusion lock at `/tmp/mecris_presence.lock` to coordinate human intervention vs. autonomous Ghost bot turns.
  - `mecris nag eval`: Heuristic evaluator for proactive reminders.

### Arm 4: Twilio & WhatsApp Messaging (`/chore-twilio-inventory`)
- **Location**: [`twilio_sender.py`](file:///Users/yebyen/w/mecris/twilio_sender.py), [`whatsapp_template_manager.py`](file:///Users/yebyen/w/mecris/whatsapp_template_manager.py)
- **The Realities of WhatsApp Messaging**:
  - **The $2–$3/mo Phone Number**: Dedicated business number managed through Twilio.
  - **A2P 10DLC Constraint**: Standard SMS is disabled without a registered 10DLC campaign. All delivery is routed via WhatsApp.
  - **The 24-Hour Session Window**: Freeform messages are allowed only if the user messaged the bot within the last 24 hours.
  - **Meta Utility Templates**: Out-of-session notifications strictly require pre-approved **UTILITY** templates with positional variables (`{{1}}`, `{{2}}`, `{{3}}`).
  - **Approved Pool**: 11 approved templates (`data/approved_templates.json`) mapped for daily briefings, budget warnings, and emergency escalations.

---

## 4. Diagnostic Discoveries & Clarifications

### The "646 Hours Overdue" Nag Mystery
When testing the CLI nagging heuristic, it reported:
> *"🚨 Arabic reviews still overdue after 646h."*

Tracing into [`services/reminder_service.py`](file:///Users/yebyen/w/mecris/services/reminder_service.py) revealed that Tier 2 escalation computes `hours_idle` by querying the timestamp of the *last sent reminder of that type* in the Neon `message_log` table. Because no reminder had been dispatched via Twilio in 26 days, it calculated the silence of the database log, not the user's actual Clozemaster practice!

### Greek Pipe Thinning
The CLI pulse dashboard highlighted:
> *"🏺 Greek Pipe Thinning: Future reviews are low. Consider PLAYING new cards to build future momentum."*

This is a key insight from the Review Pump model: when future review liabilities drop too low, you risk running out of daily review volume. Playing new cards primes the pump for steady daily accountability.

---

## 5. The "Lost" Satellite Arms of Mecris

Exploring the full repository catalog unearthed several forgotten satellite projects that will soon join the chore rotation:
- **Claude Code Tamagotchi** ([`claude-code-tamagotchi/`](file:///Users/yebyen/w/mecris/claude-code-tamagotchi)): A retro terminal digital pet reacting to development velocity and budget health.
- **TalkType Voice Engine** ([`tools/talktype/`](file:///Users/yebyen/w/mecris/tools/talktype)): Local Whisper speech-to-text service for hands-free voice logging.
- **Moon Phase Clock** ([`tools/moon-phase-clock/`](file:///Users/yebyen/w/mecris/tools/moon-phase-clock)): Android Compose circadian / lunar tracking app.
- **Urbit Gall Bot** ([`tlonbot/`](file:///Users/yebyen/w/mecris/tlonbot)): Decentralized messaging bridge to Tlon / Urbit landscape.
- **Obsidian Vault Bridge** ([`obsidian_client.py`](file:///Users/yebyen/w/mecris/obsidian_client.py)): Knowledge vault notes integration.
- **Semantic Bookmarks Index** ([`tools/chrome_bookmarks.py`](file:///Users/yebyen/w/mecris/tools/chrome_bookmarks.py)): TF-IDF search across browser research bookmarks.

---

## 6. Multi-Backend Parity & The Akamai Edge Deploy

When play-testing the Web dashboard live, we uncovered a fascinating distributed microservice nuance:
- **Android vs. Web Data Fetching**: The Android client was working seamlessly because it made dedicated Retrofit calls to `GET /budget` and queried local Health Connect sensors on-device. The Web app, conversely, assumed `GET /aggregate-status?full=true` was a monolithic snapshot containing everything.
- **The Dual Fix**:
  1. **Frontend Normalization**: Updated [`web/src/Dashboard.tsx`](file:///Users/yebyen/w/mecris/web/src/Dashboard.tsx) to fetch `GET /budget` in parallel, normalize system pulse modalities, and point local fallback to `http://localhost:8080` (FastMCP).
  2. **Rust Backend Parity**: Updated [`mecris-go-spin/sync-service/src/lib.rs`](file:///Users/yebyen/w/mecris/mecris-go-spin/sync-service/src/lib.rs) to query `budget_tracking` and `walk_inferences` on Neon Postgres, returning `today_distance_miles`, `today_steps`, `budget_remaining`, and structured `system_pulse`.
  3. **Live Akamai Deployment**: Bound `TWILIO_WHATSAPP_TEMPLATE_SID` (`HX638b7f9403e04c8fa880370f1b7a9ba1`) and deployed both WASM modules (`sync-service` + `review-pump`) live to Akamai Edge Functions (`https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app`) in **Production WhatsApp Delivery Mode**.

---

## 7. The PocketID Breakthrough, Calm Auth & Cross-Arm Parity

During live field testing on Android, we encountered two subtle distributed edge cases:

1. **Transient Notification Silencing**: While we had calmed the in-app snackbars, `AuthErrorReporter.kt` was still posting high-priority system tray notifications (`"Mecris needs your attention"`) on transient socket timeouts. We updated `report()` to strictly gate system tray notifications on `error.isPermanent == true`, guaranteeing that background Wi-Fi reconnects remain 100% silent and non-intrusive.
2. **Cross-Arm Momentum Orb Parity (Issue #283)**: A subtle semantic discrepancy arose where Web displayed **STABLE (Green Orb)** for 2/3 goals met, while Android displayed **CRITICAL (Red Orb)** because it evaluated physical walking exclusively. We formalized the [`/parity-arbitration`](file:///Users/yebyen/w/mecris/.github/skills/parity-arbitration/SKILL.md) protocol, completed a clean TDG Red-Green cycle, and aligned Android's `calculateMomentum` to the canonical 50% multi-goal threshold.
3. **The 30-Day Refresh Token Secured (🎉)**: Under full OIDC scope negotiation (`openid`, `profile`, `email`, `offline_access`), PocketID presented complete user consent and minted a hardware-encrypted 30-day sliding refresh token.

We codified both [`/chore-pocketid-inventory`](file:///Users/yebyen/w/mecris/.github/skills/chore-pocketid-inventory/SKILL.md) and [`/parity-arbitration`](file:///Users/yebyen/w/mecris/.github/skills/parity-arbitration/SKILL.md) into the codebase, ready for the release candidate soak!

---

## 8. Next Step: Sunday Lookback & 24-Hour Soak Checkpoints (4:00 PM)

Our weekend chore toolkit now spans 7 specialized inspection arms:
- `/chore-web-inventory`
- `/chore-android-inventory`
- `/chore-cli-inventory`
- `/chore-twilio-inventory`
- `/chore-moon-clock-inventory`
- `/chore-pocketid-inventory`
- `/chore-weekend-master`
- `/parity-arbitration`

### 🕯️ Sunday 4:00 PM Soak Checklist
When the next session kicks off tomorrow at 4:00 PM to evaluate `v0.0.1-rc.6` (versionCode 31):
1. **PocketID Refresh Token Stability**:
   - Verify that zero `UNKNOWN: AuthorizationException` modal interruptions occurred across the 24-hour window.
   - Confirm background token refreshes executed silently via hardware keystore.
2. **Physical Activity & Majesty Cake Status**:
   - Check the walk goal transition from 1,798 steps (car ride & hot-day pacing with Boris) past the 2,000-step threshold.
   - Verify all 3 daily goals (`arabic`, `greek`, `walk`) reflect **ALL_CLEAR (🍰 Gold Orb)** across both Android and Web.
3. **Cross-Arm Parity Validation**:
   - Run `/chore-weekend-master` to verify that Android, Web, and Akamai WASM edge agree on all aggregate metrics.
   - Evaluate whether `0.0.1-rc.6` is ready for GA promotion or if one more chore pass is warranted.
