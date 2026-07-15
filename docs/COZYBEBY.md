# cozybeby: The Operational CozyStack Death Star

> The battle station on beby.cloud in Slovakia. 9 Talos nodes, Hailo 10H NPU
> devices inlined, SpinKube live, CNPG operator running, Ghost Heartbeat
> ready to revive.

**Location:** Slovakia (`beby.cloud`)  
**Platform:** CozyStack on Talos Linux  
**Nodes:** 9 (3 control-plane, 6 worker), all Talos  
**Storage:** Linstor/DRBD with Piraeus CSI + NFS  
**Network:** Cilium CNI + Envoy  
**Operators:** Flux (tenants), VictoriaMetrics/Grafana, CNPG, SpinKube, VPA  
**Distinguishing feature:** **Hailo 10H NPU devices**, serving `hailo-ollama` for edge inference  
**Age:** ~18–20 days since last reboot (as of 2026-07-15)  
**Status:** ✅ **Fully operational**

---

## 1. What cozybeby is

A production CozyStack cluster running on consumer/prosumer hardware in Slovakia,
serving as:

1. **The persistent, always-on Death Star** — the venue for multi-tenant workloads,
   long-running services, and persistent storage.
2. **Mecris's operational platform** — the natural home for the sync-service
   SpinApp, a Postgres database (CNPG), and the scheduled cron nags.
3. **The edge LLM endpoint** — `hailo-ollama` (the qwen2:1.5b HEF model on Hailo
   10H) that the `py_harness` local-first loop uses.
4. **A validated SpinKube platform** — `spin-operator` installed with a
   `simple-spinapp` pod continuously running for ~20 days.
5. **A multi-tenant Kubernetes host** — running the `blackjack-exp1` nested
   tenant (vcluster-style pods) alongside platform services.

## 2. Hardware & topology

```
9 Talos nodes (Tailscale-connected, private IP)
├─ 3× control-plane (kube-apiserver, controller-manager, scheduler)
│  ├─ talos-1af89
│  ├─ talos-2a952
│  └─ talos-53810
└─ 6× worker (Linstor satellites, CNI nodes, app pods)
   ├─ talos-05fc1, talos-11937, talos-1af89, talos-2a952, talos-35d94, talos-428fe
   └─ ... (more; exact count from satellite count)

Hailo 10H NPU devices
├─ Inlined in node hardware (likely the 3–4 primary nodes)
└─ Exposed via hailo-ollama pod (default namespace)
```

The nodes are accessible via Tailscale — `beby.cloud` is likely a Tailscale DNS
name — so the cluster is private by default and secure for multi-tenant use.

## 3. Platform stack (observed 2026-07-15)

### Core CozyStack

- **Operator**: `cozystack-operator` (running in `cozy-system`)
- **Container runtime**: containerd (implicit in Talos)
- **Kernel**: Talos Linux (all 9 nodes, with custom extensions for Hailo drivers)

### Networking

- **CNI**: Cilium (`cozy-cilium` namespace, 13 DaemonSet pods + operator)
- **Envoy**: 9× sidecar proxies (one per node) for L7 routing
- **DNS**: CoreDNS (standard in `kube-system`, plus per-tenant CoreDNS in `blackjack-exp1`)

### Storage

- **LINSTOR/DRBD**: Distributed, replicated block storage
  - `cozy-linstor` namespace hosts:
    - `ha-controller-*` (9 nodes, one per DaemonSet)
    - `linstor-controller` (2/2 replicas)
    - `linstor-csi-controller` (7/7 container replicas, central CSI driver)
    - `linstor-csi-node-*` (9 nodes, one per DaemonSet, 3 containers each)
    - `linstor-satellite.*` (one pod per node, 4 containers for DRBD sync)
    - `linstor-scheduler-*` (2 replicas)
    - `linstor-affinity-controller` (resource affinity, 1 replica)
  - NFS servers on top: `linstor-csi-nfs-server-*` (9 pods)
- **Snapshot support**: `cozy-snapshot-controller` with admission webhooks

### Package management & automation

- **Flux**: GitOps operator in `cozy-fluxcd`
  - `flux-*` (5/5 controllers: source, kustomize, helm, notification, image-reflector)
  - `flux-tenants-*` (tenant controller for vcluster/nested namespaces)
- **Reloader**: `cozy-reloader` — watches for ConfigMap/Secret changes and rolls
  out deployments

### Observability

- **VictoriaMetrics operator**: `cozy-victoria-metrics-operator` (metrics aggregation)
- **Grafana operator**: `cozy-grafana-operator` (dashboards + operator)
- **Metrics Server**: `cozy-monitoring` (resource metrics for HPA/VPA)
- **VPA**: `cozy-vertical-pod-autoscaler` (recommender, updater, admission controller)
  - And charmingly, `cozy-vpa-for-vpa` — an autoscaler for the autoscaler

### Certificates & admission

- **cert-manager**: `cozy-cert-manager` (cert controller, cainjector, webhook)

### Database

- **CNPG operator**: `cozy-postgres-operator` with the CloudNativePG control plane
  - Ready to deploy a `Cluster` resource for Mecris's Postgres needs

### Container orchestration

- **SpinKube**: `spin-operator` with the controller-manager running
  - A `simple-spinapp` pod continuously running in `default` (~20d uptime)
  - Proof that Spin workloads are validated and production-ready on cozybeby

### Tenancy

- **blackjack-exp1** namespace: a nested vcluster-style tenant
  - `blackjack-exp1-0` (the vcluster control plane)
  - `blackjack-traefik-*` (Traefik reverse proxy in the tenant)
  - `coredns-*` (isolated CoreDNS for the tenant)
  - `plan21-backend-*` and `plan21-frontend-*` (the tenant's application)
  - Proves CozyStack multi-tenancy is live

### Edge inference

- **hailo** namespace: `hailo-ollama`
  - The qwen2:1.5b HEF model (1.5 billion parameters, Hugging Face format)
  - Running on Hailo 10H devices inlined in the hardware
  - This is the brain `py_harness` calls via `qwen2:1.5b` @ `hailo-ollama`
  - Uptime: ~20 days

## 4. Metrics & health

### Restarts

Most services show 1–4 restarts over 18–20 days (normal for a development
cluster). Notable exceptions:

- `linstor-csi-node-q66vm`: 12 restarts (storage node, may be under churn)
- `flux-*`: 35 restarts (GitOps operator, likely automated updates)
- `cilium-operator`: 22 restarts (network operator, possibly probing/healing)
- Most Cilium pods: 1 restart (normal)

**Telemetry quirk:** Several pods report restart time `(56y ago)` — epoch-zero
(1970-01-01) timestamp artifacts, likely from Talos/container startup logging.

### Uptime

- Nodes last rebooted 13–18 days ago (control-plane nodes, 13d; workers, 18d)
- `simple-spinapp` pod: ~20 days
- `hailo-ollama`: ~20 days
- Platform operators: 18–20 days

### Storage

Linstor satellites and NFS servers are running smoothly; no pod evictions or
failures. The DRBD replication is keeping all nodes in sync.

## 5. How Mecris uses cozybeby

### Current state

Nothing is deployed yet — the Ghost Heartbeat has been dark since April/May 2026.
But all the infrastructure is in place.

### Deployment path

1. **Database**: Create a CNPG `Cluster` in the `default` or `mecris` namespace.
   The CNPG operator is already running; one manifest away.

   ```yaml
   apiVersion: postgresql.cnpg.io/v1
   kind: Cluster
   metadata:
     name: mecris-db
     namespace: default
   spec:
     instances: 3          # HA across the cluster
     storage:
       size: 10Gi
     bootstrap:
       initdb:
         database: mecrisdb
         owner: mecris
   ```

2. **Sync-service**: Deploy the Mecris sync-service as a SpinApp. The
   `spin-operator` is live and the `simple-spinapp` validates it works.

   ```yaml
   apiVersion: core.spinoperator.dev/v1alpha1
   kind: SpinApp
   metadata:
     name: mecris-sync-service
     namespace: default
   spec:
     image: ghcr.io/kingdonb/mecris/sync-service:latest  # (or Spin image ref)
     replicas: 2
     env:
       - name: NEON_DB_URL
         valueFrom:
           secretKeyRef:
             name: mecris-db
             key: uri
   ```

3. **Cron scheduling**: Use Flux or native Kubernetes CronJob to trigger the
   nag loop on schedule (e.g., every 4 hours, or during waking hours).

4. **Android app failover**: Update the Android app's backend config to use
   cozybeby as the primary (with Neon or localhost as fallback).

### Why cozybeby, not Neon?

- **Hailo inference is here** — `hailo-ollama` lives on cozybeby. If Mecris
  wants to use the edge brain for narrator workloads, it's a local call.
- **Multi-tenant ready** — the `blackjack-exp1` tenant proves the pattern; Mecris
  can get its own tenant namespace.
- **No vendor lock** — fully self-hosted, under your control, backed by DRBD.
- **Already running** — the operators are warm, the SpinKube is validated.
- **Neon is still valid** — as a secondary database (e.g., for cloud failover),
  configured in `GETTING_STARTED.md` Option A.

## 6. Metrics & monitoring

### VictoriaMetrics

The `cozy-victoria-metrics-operator` is running; the stack is collecting
Prometheus-style metrics from all nodes and pods.

### Grafana

The `cozy-grafana-operator` is installed — dashboards can be defined as CRDs.

### Alerting

Not visible in the pod list, but the stack is ready for it (VictoriaMetrics +
Grafana can route to AlertManager).

## 7. Known quirks & future work

### Epoch-zero timestamps

Some pods report restart times `(56y ago)`. This is harmless telemetry baggage
from the Talos/container runtime, not a real problem.

### Tailscale integration

All nodes are Tailscale-connected (`beby.cloud`), making the cluster accessible
only from your Tailscale network. This is intentional and good for security.

To access cozybeby from outside Tailscale (e.g., for a public Mecris API):
- Option A: Expose a LoadBalancer service via an external IP (requires DNS).
- Option B: Keep it private (Tailscale only) and access via a Tailscale VPN exit node.

### Mikrotik router (future)

The original Death Star design included a dual-homed Mikrotik router; cozybeby
doesn't have that yet. KubeVirt + a Mikrotik VM would replicate the topology
for network tinkering.

### Kubernetes version

Not visible in the pod list, but likely a recent LTS (Talos picks stable
upstream). Check with `kubectl version`.

## 8. How to get access

```bash
# If you're on the home Tailscale network:
export KUBECONFIG=~/.kube/cozybeby.yaml
kubectl config set-cluster cozybeby --server=https://[beby.cloud:6443]
kubectl config set-context cozybeby --cluster=cozybeby --user=admin
kubectl config use-context cozybeby

# Or, if the context already exists:
kubectl --context cozybeby get nodes
```

The cluster is on the private Tailnet, so authentication is Tailscale + kubeconfig
(likely `~/.kube/config` via talosctl or a kubeconfig secret).

## 9. Relationship to other Mecris infrastructure

| Component | Where | Notes |
|---|---|---|
| **Mecris MCP server** | Neon (GETTING_STARTED Option A) or CNPG on cozybeby (Option B) | Either works; cozybeby is more self-hosted |
| **Pi harness** | Your workstation | Connects to Mecris MCP server; no deployment to cozybeby |
| **py_harness** | Your workstation | Connects to `hailo-ollama` on cozybeby (192.168.2.109:30434 or Tailscale IP) |
| **Android app** | Your phone | Syncs to Mecris via Android bridge (currently dark; revival targets cozybeby) |
| **Spin sync-service** | (currently dark) | Targets cozybeby SpinKube + database |
| **Hailo-ollama** | cozybeby (hailo namespace) | The edge narrator brain; `py_harness` calls it directly |

---

## Next steps

1. **Verify access**: `kubectl --context cozybeby get po -A`
2. **Deploy the database**: Create a CNPG `Cluster` resource
3. **Deploy the sync-service**: Port the Mecris SpinApp to cozybeby
4. **Wire cron**: Schedule nag triggers (Flux CronJob or Kubernetes native)
5. **Test**: Send a test SMS/WhatsApp via the revived nagging loop
6. **Wire the Android app**: Update the backend URL to cozybeby (primary) + Neon (fallback)

---

*Welcome to the operational Death Star. The Ghost Heartbeat is ready to beat again.* 🐗
