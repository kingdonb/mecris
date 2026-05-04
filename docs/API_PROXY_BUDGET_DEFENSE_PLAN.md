# API Proxy Budget Defense Plan (The Internal API Intercept)

**Date**: 2026-05-02
**Status**: DRAFT / PLANNING
**Target**: Implementation required before the next billing cycle (mid-May 2026)

## 1. Executive Summary

The recent $247 token drain incident revealed a critical architectural flaw: **unmetered autonomy**. The `mecris-bot` was entrusted to manage its own loops without hard enforcement from the vendor (Helix), as Helix currently lacks a public billing API for programmatic constraints. Relying on an agent to self-report usage is a vulnerability.

To ensure this never happens again (and to protect "Luke's basement" from burning down when we switch to local GPUs), we must implement an **Internal API Intercept**—a reverse proxy layer. This proxy will sit between our LLM clients (like the `mecris-bot` GitHub Action) and the actual upstream providers (Helix, Groq, local GPUs). 

By controlling the network chokepoint, we can enforce budgets, implement circuit breakers, and track every single token with cryptographic certainty, completely out-of-band from the autonomous agent.

## 2. Architecture & Flow

```mermaid
graph TD
    A[mecris-bot (GitHub Actions)] -->|API Request| B(Mecris Edge Proxy)
    C[Local Claude CLI] -->|API Request| B
    
    B -->|Check Budget| D[(Neon Database)]
    D -.->|Budget OK| B
    
    B -->|Forward Request| E[Helix API]
    E -.->|Response + Token Counts| B
    
    B -->|Log Usage & Deduct| D
    B -.->|Response| A
    
    B -->|Anomaly / Limit Reached| F[Twilio SMS Alert]
    F -.->|Alert User| G[User Phone]
```

### Components
- **Mecris Edge Proxy**: A high-performance, edge-deployed proxy (could be built via Cloudflare Workers, a lightweight Python FastAPI service, or Rust/Axum) that implements standard Anthropic/OpenAI API interfaces.
- **Client Configuration**: `mecris-bot` and other agents will have their `ANTHROPIC_BASE_URL` (or OpenAI equivalent) configured to point to the Mecris Edge Proxy, not Helix directly.
- **Neon Database Integration**: The proxy holds the secure `NEON_DB_URL`. It intercepts requests, validates against the `budget_tracking` table, and explicitly rejects requests if funds are dry.
- **Twilio Circuit Breaker**: The proxy monitors for spikes. If it sees anomalous traffic, it drops the request and texts the user immediately.

## 3. Implementation Phases (14-Day Timeline)

With 14 days until the new billing cycle provides a fresh $100 budget, we have a clear runway to implement this defense in depth.

### Phase 1: Pass-Through & Telemetry (Days 1-4)
- **Scaffold the Proxy**: Build a service that accepts requests, attaches the real Helix API key (stored securely in the proxy's environment), and forwards them to Helix.
- **Response Parsing**: Parse the return payload from Helix to extract `usage.input_tokens` and `usage.output_tokens`.
- **Synchronous Ledger**: Connect the proxy to the Neon DB. On every successful request, synchronously write the exact token consumption to the `usage_sessions` table and decrement the `budget_tracking` balance.

### Phase 2: Hard Enforcement & Rate Limiting (Days 5-8)
- **The Budget Gate**: Before forwarding *any* request, the proxy queries the Neon database. If `remaining_budget <= 0`, the proxy immediately returns an `HTTP 402 Payment Required` or `HTTP 429 Too Many Requests`. The agent's tools (like Claude CLI) will treat this as a fatal network error and halt the context snowball.
- **Velocity Limits**: Implement a Leaky Bucket or sliding window rate limiter.
  - *Example*: Max 100,000 input tokens per hour. If a single run tries to ingest 300KB of test logs, it hits the wall.

### Phase 3: Anomaly Detection & Alerting (Days 9-11)
- **Pattern Recognition**: Define triggers for anomalous behavior.
  - Sudden spike in input payload size (e.g., >20k tokens in one shot when previous average was 2k).
  - High frequency of requests (e.g., >10 requests in 60 seconds).
- **Out-of-band Alerts**: Integrate `twilio_sender.py` logic directly into the proxy. When an anomaly is detected and the request is blocked, fire an SMS to the user with the exact metrics.

### Phase 4: Intelligent Routing (Days 12-14)
- **Provider Abstraction**: Now that we control the endpoint, we can route traffic based on the model requested or the nature of the prompt.
- **Cheaper Inference**: Route simple tasks to Groq (Llama 3) or local GPUs (Luke's basement), while preserving expensive Helix Claude tokens for high-reasoning tasks.
- **Graceful Fallback**: If Helix goes down or we run out of Helix credits, automatically route to Groq as a fallback, ensuring the system stays online but degrades gracefully to cheaper models.

## 4. Security Considerations

1. **Proxy Authentication**: The proxy must require an API key from the client (`mecris-bot`). This internal key is distinct from the Helix key. If the bot's key leaks, the attacker only gets access to our strictly rate-limited, budget-capped proxy, not our unlimited Helix account.
2. **State Isolation**: The `mecris-bot` must **never** be given the `NEON_DB_URL` directly. By moving budget tracking into the proxy, the bot returns to being a "dumb client," and the proxy acts as the omniscient warden.
3. **Failsafe**: If the proxy cannot reach the Neon database to verify the budget, it must **fail closed** (reject the request) to guarantee we do not overspend.

## 5. Conclusion

This architecture shifts accountability from the *agent* to the *infrastructure*. The agent can hallucinate, loop infinitely, or try to ingest the entire internet, but the API Proxy will act as a physical brick wall, ensuring that no request leaves our network without explicit, budgeted permission.

**Next Action**: We will leave `mecris-bot` disabled. We will begin scaffolding the `mecris-edge-proxy` service and deploy it prior to the mid-May billing cycle reset.
