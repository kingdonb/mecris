# GEMINI.md - Mecris Personal LLM Accountability System

This document provides a comprehensive overview of the Mecris project, its architecture, and how to interact with it.

## 1. Project Overview

Mecris is a persistent cognitive agent system designed to extend Claude's narrative thread beyond single sessions. It acts as a delegation system to help maintain focus, track progress, and provide strategic insight by integrating with personal data sources.

**Core Technologies:**

*   **Backend:** The primary backend is a Python [FastAPI](https://fastapi.tiangolo.com/) server. It serves as the Machine Context Provider (MCP) and aggregates data from various sources.
*   **Integrations:**
    *   **Beeminder:** Tracks goals and deadlines.
    *   **Obsidian:** Manages notes, todos, and session logs.
    *   **Twilio:** Sends SMS alerts for critical events.
    *   **Claude/Groq:** Integrates with LLMs for narrative and strategic insights.
*   **Data Storage:** A local SQLite database (`mecris_usage.db`) is used for usage tracking and budget management.
*   **Rust Component:** A Rust component (`boris-fiona-walker`) is present, but its exact role is not fully detailed in the reviewed files.
*   **TypeScript/Node.js Component:** A TypeScript/Node.js component (`mcp-server-ts`) exists, likely for a specific service or endpoint.

**Architecture:**

The system is built around a central FastAPI server that exposes a series of endpoints. These endpoints provide a unified interface to the various integrated services. The server is designed to be MCP-compliant, allowing it to be used as a tool by other AI agents.

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

To use the Mecris server with the Gemini CLI, you need to run it in `stdio` mode. This is the only supported mode for Gemini CLI integration.

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


