# 🧪 Local Verification Guide: Intelligent Reminders

This guide allows you to test the "Smart Hype-Man" logic (WASM module) locally using your real API keys *before* deploying to the cloud.

## 🎯 Goal
Verify that the Rust code correctly talks to:
1.  **OpenWeather API** (Is the weather fetching working?)
2.  **Beeminder API** (Can it see your 'bike' goal?)
3.  **Twilio API** (Can it actually send a text?)

---

## 🛠️ Step 1: Setup Local Environment

You need to feed your secrets into the local Spin runtime.

1.  **Navigate to the module:**
    ```bash
    cd boris-fiona-walker
    ```

2.  **Create a `.env` file** (Spin won't read this automatically, but we'll use it to source variables):
    ```bash
    # Create a temporary env file (DO NOT COMMIT THIS)
    touch .env.local
    ```

3.  **Add your secrets to `.env.local`:**
    ```env
    SPIN_VARIABLE_OPENWEATHER_API_KEY="your_openweather_key"
    SPIN_VARIABLE_BEEMINDER_USERNAME="kingdonb"
    SPIN_VARIABLE_BEEMINDER_API_KEY="your_beeminder_key"
    SPIN_VARIABLE_TWILIO_ACCOUNT_SID="your_sid"
    SPIN_VARIABLE_TWILIO_AUTH_TOKEN="your_token"
    SPIN_VARIABLE_TWILIO_FROM_NUMBER="+123..."
    SPIN_VARIABLE_TWILIO_TO_NUMBER="+123..."
    SPIN_VARIABLE_WEBHOOK_SECRET="test_secret"
    SPIN_VARIABLE_LATITUDE="41.6764"
    SPIN_VARIABLE_LONGITUDE="-86.2520"
    ```

---

## 🏃 Step 2: Run Locally

Use `spin up` with inline environment variables. This is the safest way to inject secrets without modifying `spin.toml`.

```bash
# Source the secrets and run
set -a && source .env.local && set +a

spin up --listen 127.0.0.1:3000
```

*Output should say: `Serving http://127.0.0.1:3000`*

---

## 🔍 Step 3: Trigger the Logic

Now, acting as the "Cron Job", trigger the check manually.

**Scenario A: The "Dry Run" (Check Logic)**
Since we haven't implemented a formal `dry_run` flag yet, this *will* attempt to send a text if conditions are met.

**To verify WITHOUT sending a text:**
1.  Check the weather for South Bend. If it's **Night** or **Bad Weather**, the system should naturally skip.
2.  **Simulate Night**: You can't easily spoof time in the real system without code changes, so focus on the HTTP response.

**Execute the Trigger:**
```bash
curl -v -X POST http://127.0.0.1:3000/check 
  -H "Authorization: Bearer test_secret"
```

### 📉 Analyzing the Response

**Response Type 1: The "Skip" (Working Correctly)**
```json
{
  "status": "success",
  "reminded": false,
  "timestamp": "...",
  "dogs": ["Boris", "Fiona"],
  "spin_watch": "working! 🎉"
}
```
*Meaning*: The logic ran, checked weather/goals, and decided *not* to nag (either because you walked, weather is bad, or it's not 2-6 PM).

**Response Type 2: The "Send" (Success)**
```json
{
  "status": "success",
  "reminded": true,
  ...
}
```
*Meaning*: It actually sent the SMS. Check your phone! 📱

**Response Type 3: The "Error" (Debug Mode)**
```json
{
  "status": "error",
  "error": "OpenWeather API error 401: Unauthorized"
}
```
*Meaning*: Your keys are wrong. Check `.env.local`.

---

## 🧹 Step 4: Cleanup

When finished, remove the local secrets file to prevent accidental commits.

```bash
rm .env.local
```

## 🚑 Troubleshooting

- **"Rate limit exceeded"**: The local key-value store might be blocking you. Restart `spin up` (it resets the in-memory KV store by default unless configured to persist).
- **"Invalid webhook secret"**: Ensure the `Authorization: Bearer ...` header matches `SPIN_VARIABLE_WEBHOOK_SECRET`.
