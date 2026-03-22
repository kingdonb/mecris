
## Conceptual Design: "Number Go Up" Reminder/Driver for Greek Reviews

### Objective:
To encourage the user to increase the Greek review stack (`numReadyForReview`) by playing more cards, aligning with the goal of building a substantial backlog.

### Current Limitations:
- Clozemaster scraper primarily provides `numReadyForReview` (a decreasing metric).
- `ellinika` Beeminder goal is autodata and likely tracks cumulative progress (e.g., Total Reviews Done), not current backlog size.
- Existing `ReviewPump` is designed for "number go down" goals.

### Proposed Mechanism: "Backlog Booster"

This mechanism will focus on *driving user behavior* to increase the `numReadyForReview` for Greek, rather than pushing data to Beeminder for `ellinika`.

#### 1. Target State Definition:
    *   **`target_greek_review_backlog_size`:** A configurable target for the number of Greek reviews the user should aim to have ready. This target would be derived from user preferences or strategic goals (e.g., "maintain at least 5000 reviews ready").
    *   **`greek_review_alert_threshold`:** A lower bound below which reminders will trigger.

#### 2. Core Logic:
    *   **Data Source:** Primarily relies on the scraped `numReadyForReview` for Greek from Clozemaster (obtained via `scripts/clozemaster_scraper.py`).
    *   **Driver Trigger:** Periodically (e.g., hourly or daily), the system checks the current `numReadyForReview` for Greek.
    *   **Action Logic:**
        *   If `current_greek_reviews < greek_review_alert_threshold` AND `current_greek_reviews < target_greek_review_backlog_size`:
            *   Trigger a reminder to "Play more Greek cards!"
        *   If `current_greek_reviews < target_greek_review_backlog_size` and the user has recently been reminded/hasn't taken action:
            *   Escalate reminder intensity or frequency (adapting the "obnoxious" requirement).

#### 3. Integration with Review Pump Multiplier Concept:
    *   The `ReviewPump`'s multiplier (1.0x to 10.0x) can be adapted to control the *aggressiveness* of the "Backlog Booster" reminders.
    *   A higher multiplier could mean:
        *   More frequent reminders.
        *   More insistent notification tone.
        *   Higher target review backlog size.
    *   This allows tuning the "obnoxiousness" level.

#### 4. "Number Go Up" Goal Structure (Conceptual):
    *   While not directly pushing to `ellinika`, this design informs a general "Number Go Up" structure:
        *   **Metric Type:** Tracks cumulative progress (e.g., Total Reviews Done) or desired state size (e.g., Target Review Backlog).
        *   **Scraping:** Requires a source for this specific metric.
        *   **Beeminder Push:** If applicable, would push the *absolute cumulative value* or the *current state size* to a Beeminder goal.
        *   **Driver/Reminder System:** Can work in conjunction with Beeminder or independently to guide user actions.

#### 5. Technical Implementation Considerations:
    *   **Reminder System:** Leverage existing notification/messaging infrastructure (e.g., Android notifications, potentially SMS via `twilio_sender`).
    *   **Configuration:** Make `target_greek_review_backlog_size` and `greek_review_alert_threshold` configurable.
    *   **State Management:** Track user interaction with reminders to avoid excessive spamming while maintaining urgency.

#### 6. GitHub Issue:
    *   Create an issue for "Design: Greek Review Backlog Booster Mechanism."
