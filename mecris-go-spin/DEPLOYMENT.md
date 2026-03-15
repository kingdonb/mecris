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
