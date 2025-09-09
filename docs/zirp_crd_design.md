# Zirp (Zirpia) CRD – High‑Level Design

## Purpose
The **Zirp** custom resource provides a Kubernetes‑native abstraction for a burstable compute budget that mirrors the economics of an AWS Burstable instance, but for our Claude‑Code proxy fleet. It
- **Encapsulates** a set of back‑end proxies (free Groq, paid Groq, paid Anthropic).
- **Tracks** a *negative‑interest‑rate* metric: the longer a request sits unreconciled, the more “debt” accrues.
- **Bills** a configurable *bill rate* (default ≈ $200 / month) and reports savings versus spend.
- **Exposes** metrics via `kube-state-metrics` so the orchestrator can steer request routing and keep the system thrift‑focused across the five Mecris projects.

## Core Concepts
| Concept | Analogy | Meaning |
|---------|---------|---------|
| **Burstable credit** | AWS t‑series credits | Accumulated “free‑tier capacity” that can be spent on requests without incurring cost. |
| **Negative interest** | Debt accrues over time | Every second a request remains unreconciled adds a small penalty to the Zirp’s credit balance. |
| **Bill rate** | Monthly instance price | Baseline cost of a fully‑provisioned Claude‑Code Max (≈ $200). Adjustable per Zirp to reflect higher or lower budgets. |
| **Surplus / Debt** | Burstable credit roll‑over | When free‑tier capacity exceeds usage, the Zirp earns surplus credits; when demand exceeds free capacity, it goes into debt (paid‑Groq/Claude spend). |

## Spec (User‑Facing Fields)
```yaml
apiVersion: infra.example.com/v1alpha1
kind: Zirp
metadata:
  name: my‑zirp
spec:
  billRateUSD: 200            # monthly budget, adjustable
  backends:
    - name: free‑groq
      type: FreeGroq          # optimistic first‑hit
    - name: paid‑groq
      type: PaidGroq          # low‑cost fallback
    - name: anthropic
      type: PaidAnthropic    # high‑cost fallback
  creditPolicy:
    accrualRate: "1s"        # how quickly free‑tier credit accumulates
    decayRate: "0.001"       # negative‑interest per second of pending work
  projectSelector:
    matchLabels:
      app: mecris            # limits Zirp to the five Mecris repos
```
*All fields are declarative; the controller reconciles them into runtime configuration for the service‑mesh‑driven proxy array.*

## Status (Observed Metrics)
| Field | Description | Prometheus metric name |
|-------|-------------|------------------------|
| `freeRequestsHandled` | Number of requests successfully served by the free‑Groq backend. | `zirp_free_requests_total` |
| `paidGroqRequestsHandled` | Requests handled by the paid‑Groq tier. | `zirp_paid_groq_requests_total` |
| `anthropicRequestsHandled` | Requests that fell back to Claude/Anthropic. | `zirp_anthropic_requests_total` |
| `creditBalance` | Current burstable credit (positive = surplus, negative = debt). | `zirp_credit_balance` |
| `debtAccumulated` | Cumulative monetary debt from paid tiers. | `zirp_debt_usd_total` |
| `savingsRealized` | Monetary value saved by using free tier (freeRequests × unit cost). | `zirp_savings_usd_total` |

These fields are automatically surfaced by **kube‑state‑metrics** so dashboards and the orchestrator can query them directly.

## Reconciliation Logic (High‑Level)
1. **Initialize** credit balance based on `billRateUSD` divided by the per‑hour cost of a Claude‑Code Max instance.
2. **Watch** incoming request CRs (or HTTP traffic intercepted by the mesh) and route to the first backend.
3. **If** the mesh reports throttling (`429`) **or** the request has been pending longer than a configurable threshold, **decrease** credit balance by the *negative interest* amount and **promote** the request to the next backend.
4. **On success**, increment the appropriate request counter and **increase** credit balance by the saved amount (free‑tier) or **record** debt (paid‑tier).
5. **Periodically** emit the status fields; the orchestrator reads them to adjust `billRateUSD` or to trigger scaling of the proxy pods.

## Benefits
- **Cost transparency**: Every request’s path (free → paid‑Groq → Anthropic) is accounted for, turning “failed free‑tier attempts” into quantifiable savings.
- **Automatic thrift**: The negative‑interest model forces the controller to favor cheaper back‑ends, only escalating when absolutely necessary.
- **Project scoping**: `projectSelector` guarantees that Zirp only influences the five Mecris repos, keeping budgets isolated.
- **Observability**: Standard Prometheus metrics let the team monitor surplus vs. debt in real time and make data‑driven budgeting decisions.

---

*The Zirp CRD thus becomes the bridge between the outside world (users, CI pipelines) and the Claude‑Code proxy array, providing a burstable, budget‑aware compute primitive that aligns with our thrift‑first strategy.*
