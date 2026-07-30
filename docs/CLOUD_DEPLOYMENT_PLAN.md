# Mecris Cloud Deployment & Service Mesh Plan

**Status**: Planning Phase  
**Target**: Public cloud deployment with seamless service mesh for Android app  
**Timeline**: Next sprint(s)

---

## Current State

| Component | Status |
|-----------|--------|
| **Server (Python MCP)** | ✅ Stable, multi-tenant auth working |
| **Android App** | ✅ Building, auth + sync working |
| **Auth (Pocket ID OIDC)** | ✅ Multi-tenant mode working |
| **Local/Standalone** | ✅ Working |
| **Multi-tenant (local)** | ✅ Working |
| **Cloud Deployment** | ❌ Not deployed |
| **OIDC Public** | ❌ Private only |
| **Service Mesh (Android)** | ❌ Manual backend selection |

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Android App                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Service Mesh Client                          │   │
│  │  • Health checks all endpoints                           │   │
│  │  • Latency-based routing                                 │   │
│  │  • Automatic failover                                    │   │
│  │  • Offline queue + replay                                │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌─────────┐     ┌───────────┐   ┌──────────┐
        │  Home   │     │  Cloud    │   │ SpinKube │
        │  Server │     │  (Fermyon │   │  (Spin   │
        │  (MCP)  │     │   /Akamai)│   │  /Fermyon)│
        └─────────┘     └───────────┘   └──────────┘
              │               │               │
              └───────────────┼───────────────┘
                              ▼
                        ┌──────────────┐
                        │  Neon/Postgres│
                        │  (Shared DB)  │
                        └──────────────┘
```

---

## Phase 1: Public OIDC & Cloud API Deployment

### 1.1 Pocket ID Public Exposure
- **Current**: `https://metnoom.urmanac.com` (local/Tailscale only)
- **Target**: Public DNS with TLS, rate limiting, DDoS protection
- **DNS**: `auth.mecris.dev` → Cloudflare → Pocket ID
- **Security**: Rate limits on `/authorize`, `/token`; bot detection

### 1.2 API Gateway Deployment
| Environment | Platform | Purpose |
|-------------|----------|---------|
| **Production** | Fermyon Spin / Fly.io | Primary API |
| **Staging** | Fly.io | Pre-prod testing |
| **Development** | Local | Dev loop |

### 1.3 Database
- **Shared Neon Postgres** (already configured)
- Connection pooling via PgBouncer
- Read replicas for read-heavy endpoints (`/languages`, `/aggregate-status`)

### 1.4 Infrastructure as Code
```yaml
# fly.toml (example)
app = "mecris-api"
primary_region = "iad"

[build]
  image = "ghcr.io/kingdonb/mecris-api:latest"

[env]
  MECRIS_MODE = "multi-tenant"
  NEON_DB_URL = "${NEON_DB_URL}"
  POCKET_ID_URL = "https://auth.mecris.dev"

[services]
  internal_port = 8080
  protocol = "tcp"
  auto_stop_machines = true
  auto_start_machines = true
```

---

## Phase 2: Android Service Mesh Client

### 2.1 Requirements
| Feature | Priority |
|---------|----------|
| Endpoint health checks | P0 |
| Latency-based routing | P0 |
| Automatic failover | P0 |
| Offline queue + replay | P1 |
| Background sync (WorkManager) | P0 |
| Screen-on during sync | P0 |
| Offline queue persistence | P1 |

### 2.2 Service Mesh Client Design

```kotlin
// app/src/main/java/com/mecris/go/mesh/ServiceMeshClient.kt
class ServiceMeshClient @Inject constructor(
    private val endpoints: List<Endpoint>,
    private val healthCheckInterval: Duration = 30.seconds,
    private val okHttpClient: OkHttpClient
) {
    private val healthyEndpoints = MutableStateFlow(emptyList<Endpoint>())
    private val currentEndpoint = MutableStateFlow<Endpoint?>(null)
    
    fun getHealthyEndpoint(): Endpoint? = currentEndpoint.value
    
    private fun startHealthChecks() {
        // Parallel health checks every 30s
        // Update healthyEndpoints flow
        // Switch currentEndpoint on failure
    }
    
    suspend fun <T> executeWithFailover(request: suspend (Endpoint) -> T): T {
        val endpoints = healthyEndpoints.value.shuffled() // randomize for load balancing
        var lastException: Exception? = null
        
        for (endpoint in endpoints) {
            try {
                return endpoint.execute(request)
            } catch (e: Exception) {
                lastException = e
                markUnhealthy(endpoint)
            }
        }
        throw lastException ?: RuntimeException("No healthy endpoints")
    }
}

data class Endpoint(
    val id: String,
    val baseUrl: String,
    val type: EndpointType,
    var isHealthy: Boolean = true,
    var lastCheck: Instant = Instant.EPOCH,
    var avgLatencyMs: Long = 0
)

enum class EndpointType { HOME_SERVER, CLOUD_FERMYON, CLOUD_AKAMAI, SPIN_KUBE }
```

### 2.3 Seamless Handoff (WiFi → Cellular)
```kotlin
// Network callback to detect connectivity changes
private val networkCallback = object : ConnectivityManager.NetworkCallback() {
    override fun onLost(network: Network) {
        // Re-evaluate endpoint health immediately
        meshClient.recheckHealth()
    }
    
    override fun onCapabilitiesChanged(network: Network, caps: NetworkCapabilities) {
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) {
            // Prefer cloud endpoints on cellular
            meshClient.preferCloudEndpoints()
        }
    }
}
```

---

## Phase 3: SpinKube / Fermyon Deployment

### 3.1 SpinKube Cluster
```yaml
# spin-operator.yaml
apiVersion: spinshark.fermyon.com/v1alpha1
kind: SpinApp
metadata:
  name: mecris-spin
  namespace: mecris
spec:
  image: ghcr.io/kingdonb/mecris-spin:latest
  replicas: 3
  executor: "spin"
  trigger:
    http:
      port: 8080
```

### 3.2 Fermyon Cloud (Backup)
- Deploy same Spin app to Fermyon Cloud as hot standby
- DNS failover via Cloudflare Load Balancer

---

## Phase 4: Android App Rewire

### 4.1 Remove Manual Backend Selection
```kotlin
// DELETE: BackendManager.kt (manual endpoint selection)
// REPLACE: ServiceMeshClient auto-discovery
```

### 4.2 Seamless Transition UX
```kotlin
@Composable
fun ConnectionStatusIndicator() {
    val meshClient = hiltViewModel<MeshViewModel>().meshClient
    val current = meshClient.currentEndpoint.collectAsState()
    
    Icon(
        imageVector = when {
            current.value?.isHealthy == true -> Icons.Default.Wifi
            current.value != null -> Icons.Default.WifiOff
            else -> Icons.Default.CloudOff
        },
        contentDescription = "Connection status",
        tint = when {
            current.value?.isHealthy == true -> Color.Green
            current.value != null -> Color.Yellow
            else -> Color.Red
        }
    )
}
```

### 4.3 Background Sync Enhancement
```kotlin
// WorkManager with mesh client
class MeshSyncWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val meshClient: ServiceMeshClient
) : CoroutineWorker(context, params) {
    
    override suspend fun doWork(): Result = meshClient.executeWithFailover { endpoint ->
        // Try each endpoint until one succeeds
        endpoint.uploadWalk(walkData)
        endpoint.triggerCloudSync()
        endpoint.triggerReminders()
    }
}
```

---

## Phase 5: OIDC Public & Security Hardening

### 5.1 Pocket ID Public Hardening
| Measure | Implementation |
|---------|----------------|
| Rate Limiting | Cloudflare: 10 req/min `/authorize`, 30 req/min `/token` |
| Bot Detection | Cloudflare Bot Fight Mode + Turnstile on `/authorize` |
| Token Binding | DPoP (RFC 9449) for access tokens |
| Device Binding | Client certificates for Android app |
| Audit Logs | Log all auth events to Neon + Cloudflare Logs |

### 5.2 Android App Security
- **Certificate Pinning** for all endpoints
- **DPoP** for all API requests
- **Encrypted SharedPreferences** for tokens
- **Biometric Re-auth** for sensitive actions

---

## Phase 6: Monitoring & Observability

### 6.1 Metrics (Prometheus + Grafana)
| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| `api_latency_p99` | API Gateway | > 2s |
| `auth_failure_rate` | Pocket ID | > 5% |
| `sync_success_rate` | Android | < 95% |
| `endpoint_health` | Mesh Client | < 2 healthy |

### 6.2 Distributed Tracing
- **Jaeger** on Fly.io
- **W3C TraceContext** propagation
- **Android**: OpenTelemetry SDK

---

## Deployment Checklist

### Pre-Deployment
- [ ] Pocket ID public DNS + TLS
- [ ] API Gateway deployed (Fly.io + Fermyon)
- [ ] SpinKube cluster deployed
- [ ] Android mesh client integrated & tested
- [ ] Load test: 1000 concurrent users
- [ ] Chaos engineering: kill endpoints, verify failover
- [ ] Penetration test on public OIDC

### Launch Sequence
1. **Staging**: Deploy to staging, run E2E tests
2. **Canary**: 5% traffic to new cloud API
3. **Rollout**: 100% to cloud, home server as fallback
4. **Android**: Roll out mesh client via Play Store (staged rollout)

### Rollback Plan
- DNS failback to home server in < 60s
- Android app falls back to local-only mode automatically
- Database unchanged (shared Neon)

---

## File Structure

```
docs/
├── ARCHITECTURE.md           # This file
├── DEPLOYMENT.md             # Step-by-step deployment guide
├── SECURITY.md               # Security hardening guide
├── ANDROID_MESH.md           # Android mesh client implementation
├── SPINKUBE_DEPLOY.md        # SpinKube deployment guide
└── INCIDENT_RESPONSE.md      # Incident runbook
```

---

## Next Steps (This Sprint)

1. [ ] Deploy Pocket ID to `auth.mecris.dev` with Cloudflare
2. [ ] Deploy API to Fly.io staging
3. [ ] Build Android mesh client prototype
2. [ ] Integration test: Android → Mesh → Staging API
3. [ ] Load test staging (1000 concurrent)
3. [ ] Deploy SpinKube cluster on Fly.io
4. [ ] Load test production endpoints
4. [ ] Cutover DNS to production

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Pocket ID public abuse | Medium | High | Cloudflare rate limits + Turnstile |
| SpinKube cold starts | High | Medium | Pre-warm + keep-alive |
| Android mesh complexity | Medium | High | Incremental rollout, feature flags |
| Neon connection limits | Low | High | PgBouncer + read replicas |
| Pocket ID downtime | Low | Critical | Multi-region OIDC (future) |

---

*Document version: 1.0*  
*Author: Mecris Team*  
*Last updated: 2026-07-30*