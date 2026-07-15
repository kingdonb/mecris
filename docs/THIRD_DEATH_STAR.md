# The Third Death Star: CozyStack on AWS — Status & Revival Assessment

> A lab notebook entry on the Death Star lineage, the AWS replica that was
> designed but never built, and what it would take to revive it in 2026.

**Source document:** [`tools/cozystack-moon-and-back/attic/CLAUDE.md`](../tools/cozystack-moon-and-back/attic/CLAUDE.md)
(design doc dated 2025-11-16, filed in the attic)

**Status: 🟡 Designed, never built.** Phase 0 complete; Phases 1–5 unchecked.
The original deadline — December 2025, when the AWS t4g free tier expired —
has passed. Revival requires re-validating the cost model.

---

## 1. The Death Star Lineage

| # | Name | What | Status |
|---|---|---|---|
| I | **First Death Star** | The original home lab: DD-WRT → Mikrotik dual-homed router → fileserver at `10.17.13.140` running the netboot stack (dnsmasq, matchbox, 5× registry pull-through caches, pihole), PXE-booting Talos nodes running CozyStack | ✅ Operational (reference topology) |
| II | **Second Death Star** | The current Kubernetes cluster (Talos/CozyStack). Runs **CNPG (CloudNativePG)** — the self-hosted PostgreSQL option for Mecris (see [GETTING_STARTED.md](GETTING_STARTED.md) §3 Option B) | ✅ Operational |
| III | **Third Death Star** | AWS free-tier replica of the home lab, ARM64, for validating the stack in the cloud before deploying to Raspberry Pi CM3 modules — and for the talk *"Home Lab to the Moon and Back"* | 🟡 Design only |

The naming convention holds up: each one is a moon-sized battle station that is
definitely fully operational, except for the parts that aren't finished.

## 2. What the Third Death Star Was Designed To Be

### Topology (deliberate mirror of home)

```
Home lab (First DS)                   AWS (Third DS)
──────────────────────                ─────────────────────────
10.17.12.0/24  front subnet     →     10.20.1.0/24   public subnet (IGW, NAT GW)
10.17.13.0/24  inner subnet     →     10.20.13.0/24  private subnet
10.17.13.140   netboot server   →     10.20.13.140   bastion (static ENI)
Mikrotik dual-homed router      →     [future] Mikrotik VM via KubeVirt
```

The bastion carries the whole netboot stack as Docker containers — dnsmasq
(DHCP), matchbox (PXE, serving Talos images from a custom
`cozy-spin-tailscale` build), five `registry:2` pull-through caches
(docker.io, gcr.io, ghcr.io, quay.io, registry.k8s.io), and pihole as
VPC-wide DNS. Talos nodes (1–3× t4g.small, ARM64) PXE-boot from it exactly
as the Pi nodes do at home.

### Design principles

1. **Fidelity over convenience** — same addressing scheme, same netboot flow,
   same DNS pattern. What works in AWS works on the Pi CM3s.
2. **Free tier or bust** — bastion on a 5hr/day ASG schedule (~150 hrs/mo),
   leaving ~600 free t4g hours/month for experiment nodes. Nodes launched
   manually for 2–3 hour windows, then terminated. Target: **< $0.10/month**
   (EBS only); a 3-node, 3-hour session cost under a penny.
3. **Zero GDPR surface** — private IPv4 only, SSH ingress restricted to the
   home IPv6 address, no public services. IPv6 dual-stack deferred to a
   later phase with an explicit compliance gate.
4. **Clean teardown** — a documented "return to $0.00" procedure: terminate
   nodes, let the bastion ASG wind down, optionally delete EBS.

### Phase plan (as designed)

- **Phase 0** — Design & budget ✅ (the only completed phase)
- **Phase 1** — VPC, subnets, IGW/NAT, security groups, DHCP options
- **Phase 2** — Bastion into the private subnet, static ENI, netboot containers
- **Phase 3** — First Talos node netboots; bootstrap CozyStack; scale to 3
- **Phase 4** — Validate: SpinKube demo workload, KubeVirt VM creation
- **Phase 5** — Cost monitoring, talk demo & slides

## 3. Why It Stalled

- The **t4g free tier expired December 2025** — the entire cost model's
  foundation. The design doc's own target date was "before December 2025."
- Attention went elsewhere (by the session logs: Hailo edge inference, the
  Android sync bridge, the Python MCP server, and latterly the Pi harness).
- The document ends mid-handoff: *"Operator is going to breakfast with
  spouse... When they return, start with: 'Welcome back! Ready to build the
  Third Death Star?'"* — a poke that sat unanswered in the attic since.

## 4. Revival Assessment (July 2026)

### Does Mecris need it?

There is a real convergence with current pain points:

- **Ghost Heartbeat**: the cloud cron/nagging path has been dark since
  April/May 2026 (Fermyon and Akamai deployments offline; the bot unseen for
  ~288h as of this writing). Mecris needs *somewhere* to run the Spin
  sync-service and scheduled nags.
- The Third DS Phase 4 explicitly lists **SpinKube** validation — i.e., the
  exact runtime the Mecris sync-service targets.
- Session logs repeatedly name the **Beby.cloud Tailnet Kubernetes cluster**
  (the Second Death Star) as the intended re-hosting target for the Spin API.

### Options, honestly ranked

| Option | Cost | Effort | Notes |
|---|---|---|---|
| **A. Host on the Second Death Star** (existing cluster, CNPG already there) | ~$0 marginal | Low | The pragmatic move. SpinKube or a Spintainer on the Tailnet cluster revives the Ghost Heartbeat without any AWS work. The session logs already point this way. |
| **B. Revive the Third DS as designed** | Unknown — t4g free tier is gone; re-price t4g.small on-demand/spot | Medium | Still valuable *as the talk demo and Pi CM3 rehearsal*, but no longer near-free. Spot + aggressive teardown could keep it in single-digit dollars/month. |
| **C. Build the Pi CM3 cluster directly** (skip the AWS rehearsal) | Hardware already owned? | High | The Third DS was always a rehearsal; if the First DS netboot stack is trusted, the rehearsal may be optional. |

**Recommendation:** A for Mecris's operational needs (revive the cloud
heartbeat on the Second Death Star), and treat B as a talk-driven project with
its own budget line — re-run the cost projection first, since every number in
the original doc assumed free-tier compute.

### If reviving (B), the checklist deltas

1. Re-price: t4g.small on-demand (~$0.0168/hr eu-west-1) or spot; the
   "5 sessions/week" scenario becomes dollars, not cents.
2. Check whether a new AWS account free tier (12-month) is available/ethical
   for the demo window.
3. The custom matchbox build (`v1.10.5-cozy-spin-tailscale`) and pinned
   container versions are 2025-era — refresh Talos/CozyStack/matchbox versions.
4. Terraform was planned but never generated — Phase 1 starts from zero code
   (though existing modules for VPC/ASG/bastion were noted as reusable).

## 5. Relationship to Mecris Documentation

- **Database**: the Second Death Star's CNPG is Option B in
  [GETTING_STARTED.md §3](GETTING_STARTED.md) — Mecris needs *a* Postgres;
  Neon and CNPG are the two battle-tested fulfillments.
- **Cloud failover**: [PI_HARNESS_ROADMAP.md](PI_HARNESS_ROADMAP.md) and the
  session logs track "revive the Spin/WASM cloud backend" as an open item;
  this doc names the candidate venues.
- **Original design**: the full, unabridged plan (security groups, ENI
  layout, DNS phases, cost tables, netboot sequence) remains in
  [`tools/cozystack-moon-and-back/attic/CLAUDE.md`](../tools/cozystack-moon-and-back/attic/CLAUDE.md).
  This document is the map; that one is the territory.

---

*"Welcome back! Ready to build the Third Death Star?" — asked 2025-11-16,
answered 2026-07-15: not yet, but we finally wrote back.* 🐗
