# Proposal for Automated Clozemaster "Reviewstack" Goal Tracking

## 1. Introduction

The "reviewstack" Beeminder goal, tracking "Cards in Review stack (Clozemaster Arabic)," is currently challenging to manage. Manual tracking leads to a significant backlog of "Ready for Review" sentences, increasing derailment risk and making it difficult to balance new learning with necessary review. This document proposes an automated solution to accurately track and predict the size of the review stack.

Our overarching goal is to bring the number of "Ready for Review" sentences down to zero by mid-June, and automation is critical to achieving this.

## 2. Current Challenges with Manual Tracking

*   **Lack of Real-time Visibility:** The true number of "Ready for Review" sentences is not immediately apparent without logging into Clozemaster and navigating to the specific language's review section.
*   **Difficulty Balancing:** It's hard to strike a balance between introducing new phrases and completing review work without clear, up-to-date data.
*   **No Predictive Insights:** The current manual system offers no way to forecast when new sentences will become "Ready for Review," leading to unexpected surges in workload.
*   **High Manual Burden:** Manually checking and logging data for Beeminder is time-consuming and prone to human error or omission.
*   **Derailment Risk:** The current "CAUTION" status of the goal highlights the immediate need for better tracking.

## 3. Proposed Automation Solution

The solution involves developing a dedicated script that interacts with Clozemaster to retrieve the necessary data and feeds it into the Mecris system for analysis and Beeminder updates.

### a. Data Source: Clozemaster API

*   **API Base URL:** `https://api.cloze.com`
*   **Authentication:** The API supports authentication via **API keys or OAuth 2.0**. User credentials will be required for secure access.

### b. Data Retrieval Strategy for "Ready for Review" Count

A direct API endpoint for the "Ready for Review" count does not appear to be publicly documented. Therefore, a more sophisticated approach is needed:

1.  **Retrieval of User-Specific Language Data:** The automation would query the Clozemaster API for all sentences associated with the user's Arabic language learning, including their current mastery levels (0%, 25%, 50%, 75%, 100%) and review history/timestamps.
2.  **Calculation of "Ready for Review":** Based on Clozemaster's spaced repetition algorithm, sentences become "Ready for Review" after a certain interval (which depends on mastery level and performance). The automation would need to:
    *   Analyze the mastery level and last review date for each sentence.
    *   Apply logic that mimics Clozemaster's internal scheduling to determine which sentences are currently "due." This might involve understanding or reverse-engineering Clozemaster's specific spaced repetition intervals.
    *   Sum these "due" sentences to get the total "Ready for Review" count.
3.  **Fallback: Web Scraping (if API is insufficient):** If replicating the review logic via the API proves too complex or unreliable, an alternative would be to programmatically access and scrape the relevant section of the Clozemaster web UI while logged in. This approach is more fragile due to UI changes but could provide a direct "Ready for Review" number.

### c. Predictive Insights

By tracking the mastery levels and review schedules, the system can:

*   **Forecast Future Review Load:** Predict when a significant number of sentences are expected to become "Ready for Review" in the coming days/weeks.
*   **Balance New Sentences:** Help inform decisions on when to introduce new sentences to avoid overwhelming the review stack.

### d. Output & Integration with Mecris/Beeminder

*   The calculated "Ready for Review" count and any predictive data would be logged.
*   This data would then be automatically submitted to the "reviewstack" Beeminder goal at a defined frequency (e.g., daily).

## 4. Technical Implementation Considerations

*   **Clozemaster API Client:** Development of a Python module (`clozemaster_client.py`) for authenticated API interactions.
*   **Authentication Management:** Secure storage and retrieval of Clozemaster API keys/OAuth tokens (e.g., via environment variables or a dedicated secrets store).
*   **Data Processing Logic:** Implementation of the algorithm to determine "Ready for Review" sentences within the Python client.
*   **Beeminder Integration:** Utilize Mecris's existing Beeminder client to send data points.
*   **Scheduling:** The automation script would be scheduled to run periodically (e.g., daily via a cron job or GitHub Actions workflow) as a background task within Mecris.

## 5. Benefits of Automation

*   **Reduced Derailment Risk:** Consistent and accurate data submission to Beeminder.
*   **Real-time Visibility:** Always know the current "Ready for Review" count.
*   **Proactive Planning:** Predict future review load, enabling better balancing of new learning and review.
*   **Motivation & Accountability:** Gamified tracking reinforces the habit of managing the review stack.
*   **Time Savings:** Eliminates the manual effort of data collection and logging.

## 6. Next Steps & Decision Points

To proceed with this automation, we need to address the following:

1.  **Clozemaster Authentication:**
    *   **Action:** Determine the preferred authentication method (API Key vs. OAuth 2.0).
    *   **Decision:** User to provide the necessary API credentials.
2.  **Data Retrieval Approach:**
    *   **Decision:** Prioritize API data analysis (more robust, but requires algorithm understanding) or consider web scraping (quicker to implement, but more fragile) as a fallback.
3.  **Automation Frequency:**
    *   **Decision:** How often should the automation run (e.g., daily, twice daily)?
4.  **Integration within Mecris:**
    *   **Decision:** Where should the new Clozemaster client and automation script reside within the Mecris project structure? (e.g., `clozemaster_client.py`, `scripts/clozemaster_tracker.py`).
