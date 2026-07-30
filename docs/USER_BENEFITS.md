# What Users Get From This Update (In Plain English)

**TL;DR**: Most users won't notice anything different. This is plumbing work so the app keeps working when the underlying protocol changes. The *real* user benefits come from the Android cloud deployment this enables — not the MCP spec update itself.

---

## What Actually Changes For You

| Area | Before | After | User Impact |
|------|--------|-------|-------------|
| **Android sync** | Works via SSE (deprecated) | Works via Streamable HTTP (current) | **None visible** — sync still happens |
| **Claude/Pi integration** | Works via stdio | Still works via stdio | **None** — unchanged |
| **Authentication** | Pocket ID Bearer tokens | Pocket ID + DPoP proofs | **More secure** — tokens can't be replayed if stolen |
| **Server discovery** | Hardcoded | `server/discover` RPC | **None visible** — clients auto-detect capabilities |
| **Background tasks** | App-level pg_notify | MCP `subscriptions/listen` | **None visible** — walk invalidation still instant |

---

## What You *Won't* See (Because We're Not Building It)

| Deprecated Feature | What It Was | Why We're Skipping |
|--------------------|-------------|-------------------|
| **Roots** | Tell server "here's my project folder" | You already pass paths in tool args; no one used this |
| **Sampling** | Server asks your LLM to generate text | Servers call OpenAI/Anthropic directly; simpler |
| **Logging** | Server sends log messages over MCP | You get logs in terminal / file / OpenTelemetry |

---

## The *Real* User Benefits (Come From Cloud Deployment, Not This Spec)

This MCP update is a **prerequisite** for the cloud deployment. The actual benefits:

| Benefit | How It Works | When You Get It |
|---------|--------------|-----------------|
| **Sync works away from home WiFi** | Cloud API + service mesh → Android fails over automatically | After cloud deploy |
| **No more "home server down = no sync"** | Multiple endpoints (home, Fly.io, Fermyon, SpinKube) | After cloud deploy |
| **Seamless WiFi → cellular handoff** | Mesh client detects network change, switches endpoint | After cloud deploy |
| **Offline queue + replay** | Android queues walks/reminders, replays when online | After cloud deploy |
| **Public Pocket ID** | `auth.mecris.dev` works anywhere, not just Tailscale | After cloud deploy |

---

## What This Costs You

| Cost | Amount |
|------|--------|
| **Setup changes** | Zero — Android app updates automatically |
| **Config changes** | Zero — same Pocket ID login |
| **Downtime** | Zero — home server keeps working during transition |
| **Privacy** | Same — your data stays in Neon; DPoP just binds tokens to your device |

---

## Why We're Doing This At All

1. **MCP 2026-07-28 deprecated SSE** — our Android bridge will stop working with compliant clients
2. **DPoP is required** — without it, stolen tokens work forever; with it, they're useless
3. **`server/discover` is required** — clients need to know what we support without guessing
4. **Cloud deployment needs modern transport** — Streamable HTTP works behind load balancers; SSE doesn't

---

## What "Nominal Conformance" Means Here

We're implementing the **minimum** to:
- ✅ Pass spec compliance checks
- ✅ Keep Pi/Claude working
- ✅ Keep Android sync working
- ✅ Enable cloud deployment (the actual value)
- ❌ Add features nobody asked for (Roots, Sampling, Tasks, etc.)

---

## Bottom Line

**This spec update = plumbing.**  
**Cloud deployment = user value.**

We're fixing the pipes so the house doesn't flood when the protocol changes. The renovation (cloud + mesh) is what gives you a better shower.

---

*Document written for users, not implementers. If you're reading this and you're not a Mecris user, it's not for you.*