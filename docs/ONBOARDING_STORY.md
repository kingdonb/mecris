# 🚀 Mecris Onboarding: The Standalone Journey

This guide describes how a new user can get started with Mecris in **Standalone Mode** without needing a cloud deployment (Spin) or a Beeminder/Clozemaster account.

## 🏁 Goal
By the end of this guide, you will have:
1. A local Mecris MCP server running.
2. The Mecris Android app installed on an emulator or phone.
3. Successfully synced "fake" walk data to see the **Green Orb** (Majesty Cake).

---

## 1. Local Server Setup

Mecris uses **Neon** (Postgres) for its brain. You'll need a free Neon account.

```bash
# 1. Clone and enter
git clone https://github.com/kingdonb/mecris.git
cd mecris

# 2. Setup environment
cp .env.example .env
# Edit .env and set NEON_DB_URL=YOUR_URL
# Set MECRIS_MODE=standalone

# 3. Install and run
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv run mcp_server.py
```

Your server is now alive at `http://localhost:8000`.

---

## 2. Android App Setup (Emulator)

If you use an emulator, it can talk to your Mac via the special IP `10.0.2.2`.

1. Open `mecris-go-project` in **Android Studio**.
2. Build and run the app on an emulator.
3. **The Disconnect:** Currently, the app has a hardcoded URL. To point it at your local server:
   - *Refactoring in progress: We are adding a settings toggle.*
   - For now, edit `MainActivity.kt`:
     ```kotlin
     private val spinBaseUrl = "http://10.0.2.2:8000/" 
     ```

---

## 3. The Standalone "First Walk"

In **Standalone Mode**, the MCP server bypasses JWT security for local requests.

1. **Open the App**: You'll see a **Red Orb** (or "Critical" status) because you haven't walked yet.
2. **Simulate a Walk**:
   - In the Android Emulator extended controls, go to **Virtual Sensors** -> **Additional Sensors**.
   - Move the "Step Counter" slider.
3. **Trigger Sync**: Press **FORCE SYNC** in the app.
4. **Result**: The app sends the step count to your local MCP server. The server updates Neon.
5. **The Majesty Cake**: Refresh the app. The orb should turn **Green** (or "Satisfied").

---

## 4. Why this matters
This flow works **without Spin**. Because your phone and your server are on the same network (or linked via VPN), the Android app talks directly to the Python brain. 

### "But I'm going for a walk outside!"
When you leave your Wi-Fi, the app will store the data locally. When you return home and open the app, it will sync the "Total for Today" to your server.

**Next Level:** If you want real-time updates while in the park, that's when you deploy the **Spin Sync Service** to the cloud.
