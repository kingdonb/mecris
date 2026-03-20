# Deploying Mecris-Go Backend

This guide covers deploying the **sync-service** to Fermyon Cloud and setting up the **Neon PostgreSQL** database.

## 1. Database Setup (Neon)

1.  Log in to your [Neon Console](https://console.neon.tech/).
2.  Create a new project (e.g., `mecris-go`).
3.  Open the **SQL Editor** in the Neon dashboard.
4.  Copy the contents of `mecris-go-spin/schema.sql` and run it to initialize the tables.
5.  Go to **Connection Details** and copy your connection string (it looks like `postgres://user:pass@host/neondb`).

## 2. Deploying to Fermyon Cloud

Ensure you have the [Spin CLI](https://developer.fermyon.com/spin/v2/install) installed and are logged in.

1.  **Login**:
    ```bash
    spin cloud login
    ```
2.  **Build & Deploy**:
    ```bash
    cd mecris-go-spin/sync-service
    spin deploy
    ```
3.  **Set Variables**:
    After deployment, you must provide the database connection string. You can do this in the Fermyon Cloud dashboard under your app's variables, or via the CLI:
    ```bash
    spin cloud variable set db_url="your_neon_connection_string"
    ```

## 3. Backend Capabilities

The deployed **sync-service** provides:
- **`POST /walks`**: Ingests walk telemetry.
- **Identity**: Decodes Pocket ID JWTs to identify the user.
- **Automation**: Saves walk history to Neon and automatically dispatches a datapoint to Beeminder.
- **Idempotency**: Uses the walk start time to prevent duplicate Beeminder entries.

## 4. Android Configuration

Update the `spinBaseUrl` in `MainActivity.kt` to point to your new Fermyon Cloud URL (e.g., `https://sync-service-xxxx.fermyon.app/`).

## 5. Setting up Failover Mode

To ensure Beeminder and language stats continue to update even if your local Python MCP server goes offline, you can enable Failover Mode:

1.  **Set Credentials**: In Fermyon Cloud, add your Clozemaster credentials to the application's variables:
    ```bash
    spin cloud variable set clozemaster_email="your_email@example.com"
    spin cloud variable set clozemaster_password="your_password"
    ```
2.  **Configure a Cron Trigger**: Because this app uses standard HTTP triggers, you must set up an external cron service (like [cron-job.org](https://cron-job.org) or a GitHub Actions scheduled workflow) to ping the failover endpoint periodically (e.g., every 15-30 minutes):
    ```
    GET https://sync-service-xxxx.fermyon.app/internal/failover-sync
    ```
    The endpoint will check the `scheduler_election` table in Neon. If the Python server's heartbeat is fresh (<90 seconds old), the Spin backend will safely ignore the request. If the heartbeat is missing or stale, the Spin backend will autonomously scrape Clozemaster and push updates.
