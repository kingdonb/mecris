# Deploying Mecris-Go Backend

This guide covers deploying the **sync-service** to Fermyon Cloud and setting up the **Neon PostgreSQL** database.

## 1. Database Setup (Neon)

1.  Log in to your [Neon Console](https://console.neon.tech/).
2.  Create a new project (e.g., `mecris-go`).
3.  Open the **SQL Editor** in the Neon dashboard.
4.  Copy the contents of `mecris-go-spin/schema.sql` and run it to initialize the tables.
5.  Go to **Connection Details** and copy your connection string (it looks like `postgres://user:pass@host/neondb`).

## 2. Deploying to the Cloud

Mecris-Go supports dual-cloud deployment for high availability and edge performance.

### A. Fermyon Cloud (Primary)
Ensure you have the [Spin CLI](https://developer.fermyon.com/spin/v2/install) installed and are logged in.

1.  **Login**:
    ```bash
    spin cloud login
    ```
2.  **Build & Deploy**:
    ```bash
    cd mecris-go-spin/sync-service
    spin cloud deploy
    ```

### B. Akamai Functions (Edge)
Akamai provides global edge performance via the `spin aka` plugin.

1.  **Deploy**:
    ```bash
    cd mecris-go-spin/sync-service
    spin aka deploy --build --no-confirm
    ```

## 3. Post-Deployment Configuration

After deployment, you must provide the database connection string and other secrets to both providers.

**Fermyon Cloud**:
```bash
spin cloud variable set db_url="your_neon_connection_string"
spin cloud variable set internal_api_key="your_secret_key"
```

**Akamai Functions**:
Secrets for Akamai are managed via the `aka` plugin or the Akamai dashboard.

## 4. Android Configuration

Update the `spinBaseUrl` in `MainActivity.kt` to point to either your Fermyon Cloud URL or your Akamai Functions URL. Using Akamai is recommended for users frequently off-VPN or traveling.

## 5. Setting up Cloud Mode (Autonomous)

To ensure Beeminder and language stats continue to update even if your local Python MCP server goes offline, you can enable Cloud Mode:

1.  **Set Credentials**: In Fermyon Cloud, add your Clozemaster credentials to the application's variables:
    ```bash
    spin cloud variable set clozemaster_email="your_email@example.com"
    spin cloud variable set clozemaster_password="your_password"
    ```

2.  **Configure a Cron Trigger**: Because this app uses standard HTTP triggers, you must set up an external cron service (like [cron-job.org](https://cron-job.org) or a Akamai Spin Cron) to ping the cloud sync endpoint periodically (e.g., every 15-30 minutes):
    ```
    POST https://sync-service-xxxx.fermyon.app/internal/cloud-sync
    ```
    The endpoint will check the `scheduler_election` table in Neon. If the Python server's heartbeat is fresh (<90 seconds old), the Spin backend will safely ignore the request. If the heartbeat is missing or stale, the Spin backend will autonomously scrape Clozemaster and push updates.

