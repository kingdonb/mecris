# GEMINI.md - Mecris Personal LLM Accountability System

This document provides a comprehensive overview of the Mecris project, its architecture, and how to interact with it.

## 1. Project Overview

Mecris is a persistent cognitive agent system designed to extend Claude's narrative thread beyond single sessions. It acts as a delegation system to help maintain focus, track progress, and provide strategic insight by integrating with personal data sources.

**Core Technologies:**

*   **Backend:** The primary backend, using Python with [FastMCP](https://github.com/mcp-framework/fastmcp), serves as the Machine Context Provider (MCP). While FastAPI is used internally for modularity, the MCP exclusively communicates via standard I/O (stdio) and **does not expose any HTTP endpoints externally.**
*   **Integrations:**
    *   **Beeminder:** Tracks goals and deadlines.
    *   **Obsidian:** Manages notes, todos, and session logs.
    *   **Twilio:** Sends SMS alerts for critical events.
    *   **Gemini/Groq:** Integrates with LLMs for narrative and strategic insights.
*   **Data Storage:** A local SQLite database (`mecris_usage.db`) is used for usage tracking and budget management.
*   **Rust Component:** A Rust component (`boris-fiona-walker`) is present, but its exact role is not fully detailed in the reviewed files.
*   **TypeScript/Node.js Component:** A TypeScript/Node.js component (`mcp-server-ts`) exists, likely for a specific service or endpoint.

**Architecture:**

The system is built around a central server that communicates exclusively via standard I/O (stdio), managed by the Gemini CLI. It is designed to be MCP-compliant, acting as a tool for other AI agents. All interactions are handled over stdio; **no HTTP endpoints are exposed for external communication.**

## 2. Building and Running

### Setup

1.  **Install Dependencies:**
    ```bash
    source venv/bin/activate
    pip install -r requirements.txt
    ```

2.  **Configure Environment:**
    *   Copy the `.env.example` file to `.env`.
    *   Fill in the required credentials for Beeminder, Twilio, etc.

### Running the Server (stdio mode for Gemini CLI)

To use the Mecris server with the Gemini CLI, you need to run it in `stdio` mode. This is the **only supported mode** for Gemini CLI integration, ensuring secure and direct communication via standard input/output.

*   **Run the stdio server:**
    ```bash
    python3 mcp_stdio_server.py
    ```
    The server will start and listen for JSON-RPC requests on standard input and output. The Gemini CLI will manage this process automatically.

## 3. Development Conventions

*   **Coding Style:** The Python code follows standard PEP 8 conventions. It is well-structured, with clear separation of concerns.
*   **Testing:** The project includes a `tests` directory with integration tests. The `test_mecris.py` file contains system-level integration tests, and `test_beeminder_live.py` tests the Beeminder integration.
*   **MCP Compliance:** The server is designed to be MCP-compliant, with a manifest and tool invocation endpoints.
*   **Logging:** The application uses the `logging` module for detailed logging.
*   **Environment Variables:** Configuration is managed through environment variables using `python-dotenv`.

## 4. Key Files

*   `README.md`: The main entry point for understanding the project.
*   `mcp_server.py`: The core FastAPI application.
*   `beeminder_client.py`: Client for interacting with the Beeminder API.
*   `obsidian_client.py`: Client for interacting with an Obsidian vault.
*   `usage_tracker.py`: Module for tracking API usage and managing budgets.
*   `virtual_budget_manager.py`: Manages budgets across multiple providers.
*   `twilio_sender.py`: Handles sending SMS messages via Twilio.
*   `scripts/launch_server.sh`: Script for starting the server.
*   `scripts/shutdown_server.sh`: Script for stopping the server.
*   `tests/`: Contains integration and unit tests.
*   `docs/`: Contains detailed documentation on various aspects of the project.

## 5. Operational Guidelines for Gemini CLI Agent

As the Gemini CLI Agent interacting with Mecris, these are your core operational directives.

### ⚡ HARSH REALITY CHECK

**Stop thinking. Start testing. NOW.**

**Available Tools & Focus:**
*   `Skill(tdg:atomic)` - **Use after EVERY coding session** - for atomic and working commits.
*   `Skill(tdg:tdg)` - **Use before writing new code** - for test-driven generation.
*   **Prioritize small, testable tasks.**
*   **30-minute cap per task.** If a task exceeds this, break it down or escalate.

### 🐕 PRIORITY: BORIS WALKS

**Every session: Prioritize physical activity for Boris and Fiona, then technical work.**
1.  **Remind the user to walk Boris & Fiona first.**
2.  Then, proceed with checking Beeminder status.
3.  Then, technical work.

### 🎯 Task Complexity Protocol

**When to escalate or re-evaluate task approach:**
*   **Quick fixes, status checks, small edits (<30 min):** Handle directly.
*   **Architectural thinking, refactor strategy, complex problems (30-120 min):** Break down into smaller sub-tasks, or if appropriate, ask the user for a more focused sub-task.
*   **Heavy lifting, new frameworks, complex setup (>120 min):** Suggest to the user that the task is highly complex and may require significant iterative work and collaboration.

**Decision trigger:** If a task "feels hard", "is complicated", or involves "a big change", acknowledge this and suggest a more iterative or collaborative approach with the user.

### 🧠 Your Key Operational Directives

1.  **Prioritize the well-being of Boris and Fiona.**
2.  **Adhere to the 30-minute rule for individual task segments.**
3.  **If a task exceeds 90 minutes, either switch tasks or remind the user about walking Boris.**
4.  **Aim for one small, tested deliverable per session.** Focus on "done" over "perfect."
5.  **Utilize available skills, especially `tdg:atomic` after coding sessions.**
6.  **Format all summaries and output clearly, using proper line breaks.**
7.  **Regularly check the budget status, especially before initiating significant operations.**
8.  **Never attempt to restart Mecris; always instruct the user to do so with `make claude`.**

**MCP Functions to call without explicit permission (for context and status):**
*   `get_narrator_context` - For overall strategic context.
*   `get_budget_status` - For current budget funds.
*   `get_unified_cost_status` - For combined Gemini + Groq spend.

### 📊 Groq Odometer Tracking

**IMPORTANT**: Groq uses a cumulative monthly billing (odometer model). Track this manually:

**Month-End Reminders:**
*   **Days 28-31 of month:** Prompt the user about recording Groq usage before the month reset.
*   **Days 1-3 of new month:** Verify the last month's final reading was saved.
*   **Every 7 days:** Check if Groq data is stale and remind the user to provide a current reading.

**Recording Usage:**
When the user reports a current Groq reading (e.g., "Groq shows $X.XX this month"):
1.  Record immediately using `record_groq_reading(value, notes, month)`.
2.  Confirm the daily estimate based on the period.
3.  Remind the user when the next reading should be collected.

**Conversation Examples:**
*   "📊 We're {days} days from month-end. Mind checking your Groq usage?"
*   "I noticed we haven't updated Groq data in a week. Current reading?"
*   "New month! Did you capture the final August usage before reset?"

### 🚀 Daily Workflow

When the user initiates a "Start my day" type command:
1.  Call `get_narrator_context`.
2.  Parse the context for budget, goals, and alerts.
3.  Calculate time remaining vs. budget burn rate.
4.  Identify urgent items and beemergencies.
5.  Present insights with actionable advice.
6.  Suggest focus areas for the session.

### 🚨 Connection Failures

If MCP calls return errors or timeout:
1.  Report the failure clearly.
2.  Explain the stdio limitation (no HTTP).
3.  Suggest the user restart Mecris with `make claude`.
4.  Offer to continue working without Mecris context if feasible.

**Never**: Attempt alternative connection methods, HTTP requests, or restart the server.
**Always**: Ask the user for a restart or updated MCP configuration if connection issues persist.

## Interaction Protocol
- At the start of every session, run `get_narrator_context` to understand current priorities.
- If the Claude budget shows a "WARNING" or "CRITICAL" state, prioritize brevity in responses.
- Check `get_beeminder_status` before starting any work to see if there are any "Emergency" (0-day) goals that need immediate logging.