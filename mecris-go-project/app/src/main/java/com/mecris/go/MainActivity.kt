package com.mecris.go

import android.content.Intent
import android.os.Bundle
import android.util.Log
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.animateColor
import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.PermissionController
import androidx.health.connect.client.contracts.ExerciseRouteRequestContract
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.lifecycleScope
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.mecris.go.auth.AuthState
import com.mecris.go.auth.PocketIdAuth
import com.mecris.go.health.DataQualityReport
import com.mecris.go.health.HealthConnectManager
import com.mecris.go.health.WalkDataSummary
import com.mecris.go.health.WalkHeuristicsWorker
import com.mecris.go.sync.SyncServiceApi
import com.mecris.go.sync.WalkDataSummaryDto
import com.mecris.go.sync.PersistenceManager
import com.mecris.go.sync.DashboardCache
import kotlinx.coroutines.launch
import java.time.Instant
import retrofit2.HttpException
import com.google.gson.Gson
import com.mecris.go.sync.SyncResponse
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.concurrent.TimeUnit
import kotlin.math.sin

class MainActivity : ComponentActivity() {

    private lateinit var pocketIdAuth: PocketIdAuth
    private lateinit var healthConnectManager: HealthConnectManager
    private lateinit var persistenceManager: PersistenceManager

    private val spinBaseUrl = "https://mecris-sync-v2-r0r86pso.fermyon.app/" 
    private val syncApi = SyncServiceApi.create(spinBaseUrl)

    private val authResultLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        pocketIdAuth.handleAuthorizationResponse(result.data)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        pocketIdAuth = PocketIdAuth(this)
        healthConnectManager = HealthConnectManager(this)
        persistenceManager = PersistenceManager(this)

        setupWorkManager()

        val requestPermissionActivityContract = PermissionController.createRequestPermissionResultContract()
        
        // Surgical refresh state
        var refreshTrigger by mutableIntStateOf(0)

        val requestForegroundPermissions = registerForActivityResult(requestPermissionActivityContract) { granted ->
            Log.d("MainActivity", "Foreground Permissions Result: $granted")
            refreshTrigger++
        }

        // Route permissions are high-sensitivity and require a per-session request
        val requestRoutePermission = registerForActivityResult(ExerciseRouteRequestContract()) { routeResult ->
            Log.d("MainActivity", "Route Permission Result: $routeResult")
            refreshTrigger++
        }

        val requestBackgroundPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            Log.d("MainActivity", "Background Permission Result: $granted")
            refreshTrigger++
        }

        setContent {
            MecrisTheme {
                MecrisDashboard(
                    auth = pocketIdAuth,
                    healthManager = healthConnectManager,
                    syncApi = syncApi,
                    persistenceManager = persistenceManager,
                    authResultLauncher = authResultLauncher,
                    refreshTrigger = refreshTrigger,
                    onRefreshRequested = { refreshTrigger++ },
                    onRequestForeground = { 
                        try {
                            Log.d("MainActivity", "Launching foreground request: ${healthConnectManager.foregroundPermissions}")
                            requestForegroundPermissions.launch(healthConnectManager.foregroundPermissions) 
                        } catch (e: Exception) {
                            Log.e("MainActivity", "Failed to launch foreground request: ${e.message}")
                            Toast.makeText(this@MainActivity, "Could not open permission dialog. Please check Health Connect settings.", Toast.LENGTH_LONG).show()
                        }
                    },
                    onRequestRoute = { sessionId ->
                        try {
                            Log.d("MainActivity", "Launching per-session route request for: $sessionId")
                            requestRoutePermission.launch(sessionId) 
                        } catch (e: Exception) {
                            Log.e("MainActivity", "Failed to launch route request: ${e.message}")
                            Toast.makeText(this@MainActivity, "Could not open permission dialog.", Toast.LENGTH_LONG).show()
                        }
                    },
                    onRequestBackground = { 
                        try {
                            Log.d("MainActivity", "Launching background request: ${healthConnectManager.backgroundPermission}")
                            requestBackgroundPermission.launch(healthConnectManager.backgroundPermission) 
                        } catch (e: Exception) {
                            Log.e("MainActivity", "Failed to launch background request: ${e.message}")
                            Toast.makeText(this@MainActivity, "Could not open permission dialog. Please check Health Connect settings.", Toast.LENGTH_LONG).show()
                        }
                    },
                    onOpenSettings = {
                        val intent = Intent(HealthConnectClient.ACTION_HEALTH_CONNECT_SETTINGS)
                        try {
                            startActivity(intent)
                        } catch (e: Exception) {
                            Log.e("MainActivity", "Failed to open settings: ${e.message}")
                            Toast.makeText(this@MainActivity, "Could not open Health Connect settings", Toast.LENGTH_SHORT).show()
                        }
                    }
                )
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        if (::pocketIdAuth.isInitialized) {
            pocketIdAuth.dispose()
        }
    }

    private fun setupWorkManager() {
        val workManager = WorkManager.getInstance(this)
        val walkCheckRequest = PeriodicWorkRequestBuilder<WalkHeuristicsWorker>(
            15, TimeUnit.MINUTES
        ).build()

        workManager.enqueueUniquePeriodicWork(
            "WalkHeuristicsSync",
            androidx.work.ExistingPeriodicWorkPolicy.KEEP,
            walkCheckRequest
        )
    }
}

@Composable
fun MecrisTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = Color(0xFF00E5FF),
            secondary = Color(0xFF00C853),
            background = Color(0xFF121212),
            surface = Color(0xFF1E1E1E)
        ),
        content = content
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MecrisDashboard(
    auth: PocketIdAuth,
    healthManager: HealthConnectManager,
    syncApi: SyncServiceApi,
    persistenceManager: PersistenceManager,
    authResultLauncher: ActivityResultLauncher<Intent>,
    refreshTrigger: Int,
    onRefreshRequested: () -> Unit,
    onRequestForeground: () -> Unit,
    onRequestRoute: (String) -> Unit,
    onRequestBackground: () -> Unit,
    onOpenSettings: () -> Unit
) {
    val authState by auth.authState.collectAsState()
    val scope = rememberCoroutineScope()
    val cache = remember { persistenceManager.loadDashboard() }
    
    var walkData by remember { mutableStateOf<WalkDataSummary?>(cache?.walkData) }
    var budgetAmount by remember { mutableStateOf<Double?>(cache?.budgetAmount) }
    var languageStats by remember { mutableStateOf<List<com.mecris.go.sync.LanguageStatDto>>(cache?.languageStats ?: emptyList()) }
    var homeServerActive by remember { mutableStateOf<Boolean?>(cache?.homeServerActive) }
    var isLoading by remember { mutableStateOf(false) }
    var isFetching by remember { mutableStateOf(persistenceManager.isCacheStale()) }

    var fetchError by remember { mutableStateOf<String?>(null) }
    var syncStatus by remember { mutableStateOf("Ready") }
    var lastSyncTime by remember { mutableStateOf(cache?.lastSyncTime ?: "") }
    
    // UI State
    var showSystemHealth by remember { mutableStateOf(false) }
    
    // Lifecycle listener to refresh on resume (with 30s debounce to prevent loops)
    val lifecycleOwner = androidx.lifecycle.compose.LocalLifecycleOwner.current
    var lastResumeRefresh by remember { mutableLongStateOf(0L) }
    
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                val now = System.currentTimeMillis()
                if (now - lastResumeRefresh > 30000L) { // 30 second debounce
                    Log.d("MecrisDashboard", "Activity resumed, triggering surgical refresh")
                    lastResumeRefresh = now
                    onRefreshRequested()
                } else {
                    Log.d("MecrisDashboard", "Activity resumed, skipping refresh (debounced)")
                }
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    // Opt-out preferences
    var collectDistance by remember { mutableStateOf(true) }
    var collectGpsRoutes by remember { mutableStateOf(true) }

    // Navigation: Handle system back press
    BackHandler(enabled = showSystemHealth) {
        showSystemHealth = false
    }

    val forceSync = {
        // Trigger parent refresh which will bypass cache
        onRefreshRequested()
        
        scope.launch {
            isLoading = true
            syncStatus = "Syncing..."
            
            val currentWalk = healthManager.fetchRecentWalkData()
            walkData = currentWalk
            
            auth.getValidAccessToken { token ->
                if (token != null) {
                    scope.launch {
                        try {
                            val dto = WalkDataSummaryDto(
                                start_time = currentWalk.startTime.toString(),
                                end_time = Instant.now().toString(),
                                step_count = currentWalk.totalSteps.toInt(),
                                distance_meters = if (collectDistance) currentWalk.totalDistanceMeters else 0.0,
                                distance_source = if (collectDistance) currentWalk.distanceSource else "Opt-out",
                                confidence_score = 0.9,
                                gps_route_points = if (collectGpsRoutes) currentWalk.routePointCount else 0,
                                timezone = ZoneId.of("America/New_York").id
                            )
                            syncApi.uploadWalk("Bearer $token", dto)
                            syncStatus = "Success"
                            lastSyncTime = LocalDateTime.now().format(DateTimeFormatter.ofPattern("HH:mm"))
                        } catch (e: Exception) {
                            syncStatus = "Error"
                            Log.e("MecrisDashboard", "Sync failed: ${e.message}")
                        } finally {
                            isLoading = false
                        }
                    }
                } else {
                    syncStatus = "Auth Required"
                    isLoading = false
                }
            }
        }
    }

    LaunchedEffect(refreshTrigger) {
        val isStale = persistenceManager.isCacheStale()
        // Only skip if this is the initial launch AND cache is fresh
        if (refreshTrigger == 0 && !isStale) {
            Log.d("MecrisDashboard", "Initial launch with fresh cache, skipping fetch.")
            isFetching = false
            return@LaunchedEffect
        }

        Log.d("MecrisDashboard", "Refreshing walk data (Trigger: $refreshTrigger, Stale: $isStale)")
        isFetching = true
        fetchError = null
        walkData = healthManager.fetchRecentWalkData()
        
        auth.getValidAccessToken { token ->
            if (token != null) {
                scope.launch {
                    try {
                        val response = syncApi.getBudget("Bearer $token")
                        budgetAmount = response.remaining_budget

                        val healthResponse = syncApi.getHealth("Bearer $token")
                        homeServerActive = healthResponse.home_server_active
                        
                        // Proactively trigger failover sync (Spin will skip if Home is active)
                        try {
                            syncApi.triggerFailoverSync("Bearer $token")
                        } catch (se: HttpException) {
                            val errorBody = se.response()?.errorBody()?.string()
                            val detail = try {
                                Gson().fromJson(errorBody, SyncResponse::class.java).message
                            } catch (e: Exception) {
                                errorBody ?: se.message()
                            }
                            Log.w("MecrisDashboard", "Failover sync trigger failed ($detail)")
                        } catch (se: Exception) {
                            Log.w("MecrisDashboard", "Failover sync trigger skipped/failed: ${se.message}")
                        }

                        val langResponse = syncApi.getLanguages("Bearer $token")
                        languageStats = langResponse.languages
                        
                        // Save to cache
                        val now = LocalDateTime.now().format(DateTimeFormatter.ofPattern("HH:mm"))
                        lastSyncTime = now
                        persistenceManager.saveDashboard(DashboardCache(
                            walkData = walkData,
                            budgetAmount = budgetAmount,
                            languageStats = languageStats,
                            homeServerActive = homeServerActive,
                            lastSyncTime = now
                        ))
                    } catch (e: HttpException) {
                        val errorBody = e.response()?.errorBody()?.string()
                        val detail = try {
                            Gson().fromJson(errorBody, SyncResponse::class.java).message
                        } catch (ex: Exception) {
                            errorBody ?: e.message()
                        }
                        Log.e("MecrisDashboard", "Failed to fetch remote data: $detail")
                        fetchError = detail
                    } catch (e: Exception) {
                        Log.e("MecrisDashboard", "Failed to fetch remote data: ${e.message}")
                        fetchError = e.message ?: "Unknown error"
                    } finally {
                        isFetching = false
                    }
                }
            } else {
                isFetching = false
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("MECRIS NEURAL LINK", letterSpacing = 2.sp, fontWeight = FontWeight.Black) },
                actions = {
                    IconButton(onClick = { showSystemHealth = !showSystemHealth }) {
                        Icon(if (showSystemHealth) Icons.Default.Info else Icons.Default.Settings, contentDescription = "System Health")
                    }
                    IconButton(onClick = { forceSync() }, enabled = !isLoading) {
                        Icon(Icons.Default.Refresh, contentDescription = "Force Sync")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color.Black,
                    titleContentColor = Color(0xFF00E5FF)
                )
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp)
        ) {
            if (showSystemHealth) {
                SystemHealthScreen(
                    auth = auth,
                    authState = authState,
                    authResultLauncher = authResultLauncher,
                    healthManager = healthManager,
                    walkData = walkData,
                    collectDistance = collectDistance,
                    onCollectDistanceChange = { collectDistance = it },
                    collectGpsRoutes = collectGpsRoutes,
                    onCollectGpsRoutesChange = { collectGpsRoutes = it },
                    onRequestForeground = { 
                        Log.d("MainActivity", "Launching foreground request: ${healthManager.foregroundPermissions}")
                        onRequestForeground() 
                    },
                    onRequestRoute = onRequestRoute,
                    onRequestBackground = onRequestBackground,
                    onOpenSettings = onOpenSettings
                )
            } else {
                MainNeuralDashboard(
                    walkData = walkData,
                    budgetAmount = budgetAmount,
                    languageStats = languageStats,
                    homeServerActive = homeServerActive,
                    syncStatus = syncStatus,
                    lastSyncTime = lastSyncTime,
                    isLoading = isLoading,
                    isFetching = isFetching,
                    fetchError = fetchError,
                    collectDistance = collectDistance,
                    collectGpsRoutes = collectGpsRoutes,
                    onForceSync = { forceSync() },
                    onOpenSystemHealth = { showSystemHealth = true },
                    onRequestRoute = onRequestRoute,
                    onMultiplierChange = { name, multiplier ->
                        scope.launch {
                            try {
                                val token = auth.getAccessTokenSuspend()
                                if (token != null) {
                                    syncApi.updateMultiplier(
                                        "Bearer $token",
                                        com.mecris.go.sync.MultiplierRequestDto(name, multiplier)
                                    )
                                    // Trigger a surgical refresh via parent
                                    onRefreshRequested()
                                }
                            } catch (e: Exception) {
                                Log.e("MecrisApp", "Failed to update multiplier: ${e.message}")
                            }
                        }
                    }
                )
            }
        }
    }
}

@Composable
fun MainNeuralDashboard(
    walkData: WalkDataSummary?,
    budgetAmount: Double?,
    languageStats: List<com.mecris.go.sync.LanguageStatDto>,
    homeServerActive: Boolean?,
    syncStatus: String,
    lastSyncTime: String,
    isLoading: Boolean,
    isFetching: Boolean,
    fetchError: String?,
    collectDistance: Boolean,
    collectGpsRoutes: Boolean,
    onForceSync: () -> Unit,
    onOpenSystemHealth: () -> Unit,
    onRequestRoute: (String) -> Unit,
    onMultiplierChange: (String, Double) -> Unit
) {
    Text(
        text = "SYSTEM MOMENTUM",
        style = MaterialTheme.typography.labelSmall,
        color = Color.Gray
    )
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(200.dp)
    ) {
        val hasWalked = walkData?.isWalkInferred == true
        val hasSteps = (walkData?.totalSteps ?: 0L) > 1500
        val isStable = hasWalked || hasSteps

        val momentumValue = if (isFetching) 0.5f else if (isStable) 0.9f else 0.2f
        val momentumColor = if (isFetching) Color.White else if (isStable) Color(0xFF00C853) else Color(0xFFFF1744)

        MomentumVisualizer(momentum = momentumValue, overrideColor = if (isFetching) Color.White else null)

        Column(modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 8.dp),
               horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = if (isFetching) "FETCHING..." else if (isStable) "STABLE" else "CRITICAL",
                style = MaterialTheme.typography.labelLarge,
                color = if (isFetching) Color.White else if (isStable) Color(0xFF00C853) else Color(0xFFFF1744),
                fontWeight = FontWeight.ExtraBold,
                letterSpacing = 2.sp
            )
            if ((walkData?.walkingSessionsCount ?: 0) > 0) {
                Text(
                    text = "${walkData?.walkingSessionsCount} SESSIONS DETECTED",
                    style = MaterialTheme.typography.labelSmall,
                    color = Color(0xFF00E5FF),
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }

    // Sync Status Row
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically
    ) {
        // System Health Indicator
        if (homeServerActive != null) {
            val statusColor = if (homeServerActive!!) Color(0xFF00C853) else Color(0xFFFFD600)
            val statusLabel = if (homeServerActive!!) "HOME: ONLINE" else "CLOUD: FAILOVER"
            Surface(
                color = statusColor.copy(alpha = 0.2f),
                shape = RoundedCornerShape(4.dp),
                modifier = Modifier.padding(end = 8.dp)
            ) {
                Text(
                    text = statusLabel,
                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                    style = MaterialTheme.typography.labelSmall,
                    color = statusColor,
                    fontWeight = FontWeight.ExtraBold
                )
            }
        }

        Text(
            text = "CLOUD SYNC: ",
            style = MaterialTheme.typography.labelSmall,
            color = Color.Gray
        )
        Text(
            text = if (lastSyncTime.isEmpty()) "READY" else "$syncStatus ($lastSyncTime)",
            style = MaterialTheme.typography.labelSmall,
            color = if (syncStatus == "Success") Color(0xFF00C853) else if (syncStatus == "Error") Color.Red else Color.LightGray,
            fontWeight = FontWeight.Bold
        )

        Spacer(modifier = Modifier.width(16.dp))

        TextButton(
            onClick = onForceSync,
            modifier = Modifier.height(32.dp),
            enabled = !isLoading
        ) {
            Text(if (isLoading) "SYNCING..." else "FORCE SYNC", 
                 style = MaterialTheme.typography.labelSmall, 
                 color = Color(0xFF00E5FF))
        }
    }

    Spacer(modifier = Modifier.height(16.dp))

    // GPS Route Opportunity! (The Christmas Tree)
    val sessionId = walkData?.consentableSessionId
    if (sessionId != null) {
        val infiniteTransition = rememberInfiniteTransition(label = "christmas_tree")
        val glowColor by infiniteTransition.animateColor(
            initialValue = Color(0xFF00C853), // Green
            targetValue = Color(0xFF00E5FF),  // Cyan
            animationSpec = infiniteRepeatable(
                animation = tween(1000, easing = LinearEasing),
                repeatMode = RepeatMode.Reverse
            ),
            label = "glow"
        )

        Button(
            onClick = { onRequestRoute(sessionId) },
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 8.dp)
                .background(Brush.horizontalGradient(listOf(Color(0xFF004D40), Color(0xFF006064))), shape = RoundedCornerShape(8.dp)),
            colors = ButtonDefaults.buttonColors(containerColor = Color.Transparent),
            elevation = ButtonDefaults.buttonElevation(defaultElevation = 8.dp)
        ) {
            Text(
                "🌟 UNLOCK GPS ROUTE 🌟",
                style = MaterialTheme.typography.labelLarge,
                color = glowColor,
                fontWeight = FontWeight.Black,
                letterSpacing = 1.sp
            )
        }
        Spacer(modifier = Modifier.height(16.dp))
    }

    // Data Quality Alert (Compact link to settings)
    walkData?.let { data ->
        val hasDistanceIssue = data.qualityReport.issues.any { it.contains("distance", ignoreCase = true) } && collectDistance
        val hasGpsIssue = data.qualityReport.issues.any { it.contains("GPS", ignoreCase = true) } && collectGpsRoutes

        if (hasDistanceIssue || hasGpsIssue) {
            Surface(
                onClick = onOpenSystemHealth,
                color = Color(0xFF332B00), // Dark yellow
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier.padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("⚠️", fontSize = 20.sp)
                    Spacer(modifier = Modifier.width(12.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text("DATA QUALITY ALERT", style = MaterialTheme.typography.labelSmall, color = Color(0xFFFFD600), fontWeight = FontWeight.Bold)
                        Text("System is reporting degraded telemetry. Click to resolve.", style = MaterialTheme.typography.bodySmall, color = Color.White)
                    }
                }
            }
            Spacer(modifier = Modifier.height(16.dp))
        }
    }

    OdometerView(
        value = budgetAmount ?: 0.0,
        label = if (budgetAmount != null) "VIRTUAL BUDGET" else "VIRTUAL BUDGET (FETCHING...)",
        digitColor = Color(0xFFFFD600)
    )

    Spacer(modifier = Modifier.height(8.dp))
    val miles = (walkData?.totalDistanceMeters ?: 0.0) / 1609.34
    OdometerView(
        value = miles,
        label = "TODAY'S DISTANCE",
        symbol = "",
        suffix = "MI",
        digitColor = Color(0xFF00E5FF),
        digits = 4,
        decimalPlaces = 2
    )

    if ((walkData?.routePointCount ?: 0) > 0) {
        Spacer(modifier = Modifier.height(16.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.Center,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text("📍", fontSize = 16.sp)
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = "${walkData?.routePointCount} GPS POINTS CAPTURED",
                style = MaterialTheme.typography.labelSmall,
                color = Color(0xFF00C853),
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp
            )
        }
    }
    
    Spacer(modifier = Modifier.height(24.dp))
    
    Text(
        text = "LANGUAGE LIABILITIES (THE REVIEW PUMP)",
        style = MaterialTheme.typography.labelSmall,
        color = Color.Gray
    )
    
    Spacer(modifier = Modifier.height(12.dp))
    
    if (languageStats.isEmpty()) {
        Text(
            text = if (isFetching) "FETCHING..." else if (fetchError != null) "SYNC ERROR" else "NO REVIEWS",
            style = MaterialTheme.typography.bodySmall,
            color = if (fetchError != null) Color(0xFFFF1744) else Color.DarkGray
        )
    } else {
        languageStats.forEach { stat ->
            ReviewPumpWidget(
                stat = stat,
                onMultiplierChange = onMultiplierChange
            )
            Spacer(modifier = Modifier.height(16.dp))
        }
    }
}

@Composable
fun ReviewPumpWidget(
    stat: com.mecris.go.sync.LanguageStatDto,
    onMultiplierChange: (String, Double) -> Unit
) {
    // 1. OPTIMISTIC STATE: We keep a local copy of the multiplier so the UI reacts instantly
    var localMultiplier by remember(stat.name, stat.pump_multiplier) { 
        mutableStateOf(stat.pump_multiplier ?: 1.0) 
    }
    
    val leverName = com.mecris.go.sync.ReviewPumpCalculator.getLeverName(localMultiplier)
    val targetFlowRate = com.mecris.go.sync.ReviewPumpCalculator.calculateTargetFlowRate(localMultiplier, stat.current, stat.tomorrow)
    
    val accentColor = if (stat.name.equals("ARABIC", ignoreCase = true)) Color(0xFFFFD600) 
                      else if (stat.name.equals("GREEK", ignoreCase = true)) Color(0xFF00E5FF) 
                      else Color.White

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .then(if (!stat.has_goal) Modifier.alpha(0.6f) else Modifier),
        color = Color(0xFF1E1E1E),
        shape = RoundedCornerShape(12.dp),
        border = androidx.compose.foundation.BorderStroke(1.dp, accentColor.copy(alpha = 0.3f))
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = stat.name.uppercase(),
                            style = MaterialTheme.typography.titleMedium,
                            color = accentColor,
                            fontWeight = FontWeight.Black,
                            letterSpacing = 1.sp
                        )
                        if (!stat.has_goal) {
                            Spacer(modifier = Modifier.width(8.dp))
                            Surface(
                                color = Color.DarkGray,
                                shape = RoundedCornerShape(4.dp)
                            ) {
                                Text(
                                    text = "NO GOAL",
                                    modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp),
                                    style = MaterialTheme.typography.labelSmall,
                                    color = Color.LightGray,
                                    fontSize = 8.sp
                                )
                            }
                        }
                    }
                    Text(
                        text = "DEBT: ${stat.current} CARDS",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color.Gray
                    )
                }
                
                Column(horizontalAlignment = Alignment.End) {
                    Surface(
                        color = accentColor.copy(alpha = 0.1f),
                        shape = RoundedCornerShape(4.dp)
                    ) {
                        Text(
                            text = leverName.uppercase(),
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                            style = MaterialTheme.typography.labelSmall,
                            color = accentColor,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Liability Numbers
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text("TOMORROW", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
                    Text("+${stat.tomorrow}", style = MaterialTheme.typography.titleSmall, color = Color.White, fontWeight = FontWeight.Bold)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text("7 DAY", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
                    Text("+${stat.next_7_days}", style = MaterialTheme.typography.titleSmall, color = Color.White, fontWeight = FontWeight.Bold)
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // The Pressure Gauge
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(80.dp) // Taller for more impact
                    .background(Color.Black, RoundedCornerShape(8.dp))
                    .padding(8.dp),
                contentAlignment = Alignment.CenterStart
            ) {
                // Background Track
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(8.dp)
                        .background(Color(0xFF333333), RoundedCornerShape(4.dp))
                )
                
                // The Target Marker
                val maxScale = 1000.0
                val targetPos = (targetFlowRate / maxScale).coerceIn(0.1, 0.9).toFloat()
                
                Canvas(modifier = Modifier.fillMaxSize()) {
                    val x = size.width * targetPos
                    drawLine(
                        color = Color.White,
                        start = Offset(x, 0f),
                        end = Offset(x, size.height),
                        strokeWidth = 4f
                    )
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text("TARGET FLOW", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
                        // THE ONE NUMBER: Significantly bigger and bolder
                        Text(
                            text = "$targetFlowRate", 
                            style = MaterialTheme.typography.headlineLarge, 
                            color = accentColor, 
                            fontWeight = FontWeight.Black
                        )
                    }
                    
                    Column(horizontalAlignment = Alignment.End) {
                        Text("RUNWAY", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
                        Text("${stat.safebuf}D", style = MaterialTheme.typography.titleLarge, color = if (stat.safebuf < 3) Color.Red else Color(0xFF00C853), fontWeight = FontWeight.Black)
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // The Lever (Interactive Radio Spots)
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("SHIFT LEVER", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
                Row {
                    (1..7).forEach { i ->
                        val isSelected = localMultiplier.toInt() == i
                        Box(
                            modifier = Modifier
                                .padding(horizontal = 4.dp)
                                .size(32.dp) // Larger tap target
                                .background(
                                    if (isSelected) accentColor else Color(0xFF333333),
                                    RoundedCornerShape(6.dp)
                                )
                                .clickable { 
                                    // 2. IMMEDIATE FEEDBACK: Update local state before network call
                                    localMultiplier = i.toDouble()
                                    onMultiplierChange(stat.name, i.toDouble()) 
                                },
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = "${i}x",
                                style = MaterialTheme.typography.labelSmall,
                                color = if (isSelected) Color.Black else Color.Gray,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }
            }
        }
    }
}



@Composable
fun SystemHealthScreen(
    auth: PocketIdAuth,
    authState: AuthState,
    authResultLauncher: ActivityResultLauncher<Intent>,
    healthManager: HealthConnectManager,
    walkData: WalkDataSummary?,
    collectDistance: Boolean,
    onCollectDistanceChange: (Boolean) -> Unit,
    collectGpsRoutes: Boolean,
    onCollectGpsRoutesChange: (Boolean) -> Unit,
    onRequestForeground: () -> Unit,
    onRequestRoute: (String) -> Unit,
    onRequestBackground: () -> Unit,
    onOpenSettings: () -> Unit
) {
    Text(
        text = "SYSTEM HEALTH & AUTH",
        style = MaterialTheme.typography.titleMedium,
        color = Color.White,
        fontWeight = FontWeight.Bold
    )
    
    Spacer(modifier = Modifier.height(16.dp))

    // Diagnostics & Data Quality Section (Now in Settings)
    walkData?.let { data ->
        DiagnosticsSection(
            report = data.qualityReport,
            collectDistance = collectDistance,
            onCollectDistanceChange = onCollectDistanceChange,
            collectGpsRoutes = collectGpsRoutes,
            onCollectGpsRoutesChange = onCollectGpsRoutesChange,
            onOpenSourceApp = {
                // For now, this just opens Health Connect, but provides better labeling
                onOpenSettings()
            }
        )
    }

    Spacer(modifier = Modifier.height(24.dp))

    // Auth Status
    when (val state = authState) {
        is AuthState.Idle, is AuthState.Error -> {
            IntegrationCard(
                name = "POCKET ID",
                status = "Disconnected",
                description = if (state is AuthState.Error) state.message else "Login required for cloud sync"
            )
            Spacer(modifier = Modifier.height(8.dp))
            Button(onClick = { auth.authenticateWithPasskey(authResultLauncher) }, modifier = Modifier.fillMaxWidth()) {
                Text("Sign In with Pocket ID")
            }
        }
        AuthState.Loading -> CircularProgressIndicator()
        is AuthState.Authenticated -> {
            IntegrationCard(
                name = "POCKET ID",
                status = "Authenticated",
                description = "Identity & Access Management Active"
            )
        }
    }

    Spacer(modifier = Modifier.height(24.dp))

    Text("PERMISSIONS", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
    Spacer(modifier = Modifier.height(8.dp))

    val scope = rememberCoroutineScope()
    var hasForeground by remember { mutableStateOf(false) }
    var hasRoute by remember { mutableStateOf(false) }
    var hasBackground by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        hasForeground = healthManager.hasForegroundPermissions()
        hasRoute = healthManager.hasRoutePermission()
        hasBackground = healthManager.hasBackgroundPermission()
    }

    if (!hasForeground) {
        PermissionCard(
            title = "Foreground Access",
            description = "Basic health data reading",
            buttonText = "Grant",
            onGrant = onRequestForeground,
            onOpenSettings = onOpenSettings
        )
    } else {
        IntegrationCard("HEALTH CONNECT", "Connected", "Basic telemetry active")
    }

    Spacer(modifier = Modifier.height(8.dp))

    if (!hasRoute) {
        val sessionId = walkData?.consentableSessionId
        PermissionCard(
            title = "Route Access",
            description = if (sessionId != null) {
                "Consent required for recent walk to read GPS route."
            } else {
                "No recent walks require consent. To enable routes:\n1. Record a walk in your fitness app with GPS on.\n2. Return here to grant consent."
            },
            buttonText = if (sessionId != null) "Grant" else "Check Settings",
            onGrant = {
                if (sessionId != null) {
                    onRequestRoute(sessionId)
                } else {
                    onOpenSettings()
                }
            },
            onOpenSettings = onOpenSettings,
            isWarning = sessionId != null // Only warn if we actually need consent and don't have it
        )
    } else {
        IntegrationCard("GPS ENGINE", "Active", "Outdoor route tracking enabled")
    }

    Spacer(modifier = Modifier.height(8.dp))

    if (!hasBackground) {
        PermissionCard(
            title = "Background Sync",
            description = "Automatic detection in pocket",
            buttonText = "Grant",
            onGrant = onRequestBackground,
            onOpenSettings = onOpenSettings,
            isWarning = true
        )
    } else {
        IntegrationCard("BACKGROUND WORKER", "Active", "Periodic heuristic polling enabled")
    }
}

// --- Reusable UI Components ---

@Composable
fun MomentumVisualizer(momentum: Float, overrideColor: Color? = null) {
    val infiniteTransition = rememberInfiniteTransition(label = "momentum")
    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 0.8f,
        targetValue = 1.2f,
        animationSpec = infiniteRepeatable(animation = tween(2000, easing = LinearEasing), repeatMode = RepeatMode.Reverse),
        label = "pulse"
    )
    val rotation by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(animation = tween(10000, easing = LinearEasing), repeatMode = RepeatMode.Restart),
        label = "rotation"
    )

    val color1 = overrideColor ?: (if (momentum > 0.5f) Color(0xFF00C853) else Color(0xFFFF1744))
    val color2 = overrideColor?.copy(alpha = 0.5f) ?: (if (momentum > 0.5f) Color(0xFF2979FF) else Color(0xFFFFEA00))

    Canvas(modifier = Modifier.fillMaxSize().graphicsLayer(scaleX = pulseScale * (0.8f + momentum * 0.4f), scaleY = pulseScale * (0.8f + momentum * 0.4f), rotationZ = rotation)) {
        drawCircle(
            brush = Brush.radialGradient(colors = listOf(color1.copy(alpha = 0.8f), color2.copy(alpha = 0.2f), Color.Transparent), center = Offset(size.width / 2, size.height / 2), radius = size.width / 2),
            radius = size.width / 2,
            center = Offset(size.width / 2, size.height / 2)
        )
    }
}

@Composable
fun OdometerView(value: Double, label: String, symbol: String = "$", suffix: String = "", digitColor: Color = Color(0xFFFFD600), digits: Int = 7, decimalPlaces: Int = 2) {
    Column(modifier = Modifier.fillMaxWidth().padding(8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = Color.Gray)
        Spacer(modifier = Modifier.height(4.dp))
        Row(modifier = Modifier.background(Color.Black, RoundedCornerShape(4.dp)).padding(horizontal = 8.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
            if (symbol.isNotEmpty()) {
                Text(symbol, color = Color.White, fontFamily = FontFamily.Monospace, fontSize = 18.sp, fontWeight = FontWeight.Bold)
                Spacer(modifier = Modifier.width(4.dp))
            }
            val totalLength = digits + (if (decimalPlaces > 0) 1 else 0)
            String.format("%0${totalLength}.${decimalPlaces}f", value).take(totalLength).forEach { char ->
                Box(modifier = Modifier.padding(horizontal = 1.dp).background(if (char == '.') Color.Transparent else Color(0xFF212121), RoundedCornerShape(2.dp)).padding(horizontal = 3.dp), contentAlignment = Alignment.Center) {
                    Text(char.toString(), color = if (char == '.') Color.White else digitColor, fontFamily = FontFamily.Monospace, fontSize = 24.sp, fontWeight = FontWeight.ExtraBold)
                }
            }
            if (suffix.isNotEmpty()) {
                Spacer(modifier = Modifier.width(4.dp))
                Text(suffix, color = Color.White, fontFamily = FontFamily.Monospace, fontSize = 18.sp, fontWeight = FontWeight.Bold)
            }
        }
    }
}

@Composable
fun IntegrationCard(name: String, status: String, description: String) {
    Surface(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp), color = Color(0xFF1E1E1E), shape = RoundedCornerShape(8.dp)) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(name, style = MaterialTheme.typography.titleSmall, color = Color.White, fontWeight = FontWeight.Bold)
                Text(status, style = MaterialTheme.typography.labelSmall, color = Color(0xFF00C853))
            }
            Text(description, style = MaterialTheme.typography.bodySmall, color = Color.LightGray)
        }
    }
}

@Composable
fun LanguageForecastCard(name: String, today: Int, tomorrow: Int, next7Days: Int, dailyRate: Double, safebuf: Int, derailRisk: String, color: Color) {
    val riskColor = when (derailRisk.uppercase()) {
        "EMERGENCY" -> Color(0xFFFF1744) // Red
        "CAUTION" -> Color(0xFFFFD600)   // Yellow
        "OFF_TRACK" -> Color(0xFFFF9100) // Orange
        else -> Color(0xFF00C853)        // Green
    }

    // Prominence logic
    val isTomorrowUrgent = tomorrow > 0
    val is7DayUrgent = next7Days > (dailyRate * 7)
    
    val tomorrowAlpha = if (isTomorrowUrgent) 1.0f else 0.4f
    val next7Alpha = if (is7DayUrgent) 1.0f else 0.4f

    Surface(modifier = Modifier.fillMaxWidth(), color = Color(0xFF1E1E1E), shape = RoundedCornerShape(8.dp)) {
        Row(modifier = Modifier.padding(12.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Column {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(name, style = MaterialTheme.typography.labelLarge, color = color, fontWeight = FontWeight.Bold)
                    Spacer(modifier = Modifier.width(8.dp))
                    Surface(color = riskColor.copy(alpha = 0.2f), shape = RoundedCornerShape(4.dp)) {
                        Text(
                            text = derailRisk.uppercase(),
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                            style = MaterialTheme.typography.labelSmall,
                            color = riskColor,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
                Text("Today: $today cards", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                Text("Runway: $safebuf days", style = MaterialTheme.typography.labelSmall, color = riskColor, fontWeight = FontWeight.Bold)
            }
            Column(horizontalAlignment = Alignment.End) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    // Tomorrow Forecast
                    Column(horizontalAlignment = Alignment.End, modifier = Modifier.alpha(tomorrowAlpha)) {
                        Text("TOMORROW", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
                        Text("+$tomorrow", style = MaterialTheme.typography.headlineSmall, color = Color.White, fontWeight = FontWeight.Black)
                    }
                    Spacer(modifier = Modifier.width(16.dp))
                    // 7-Day Forecast
                    Column(horizontalAlignment = Alignment.End, modifier = Modifier.alpha(next7Alpha)) {
                        Text("7 DAY", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
                        Text("+$next7Days", style = MaterialTheme.typography.titleMedium, color = Color.White, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
    }
}

@Composable
fun DiagnosticsSection(
    report: DataQualityReport,
    collectDistance: Boolean,
    onCollectDistanceChange: (Boolean) -> Unit,
    collectGpsRoutes: Boolean,
    onCollectGpsRoutesChange: (Boolean) -> Unit,
    onOpenSourceApp: () -> Unit
) {
    // Determine if we should even show the card (only if issues exist or opt-outs are active)
    val hasDistanceIssue = report.issues.any { it.contains("distance", ignoreCase = true) } && collectDistance
    val hasGpsIssue = report.issues.any { it.contains("GPS", ignoreCase = true) } && collectGpsRoutes
    val isExcellent = !hasDistanceIssue && !hasGpsIssue

    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = if (isExcellent) Color(0xFF1E1E1E) else Color(0xFF2D1616),
        shape = RoundedCornerShape(8.dp),
        border = if (isExcellent) null else androidx.compose.foundation.BorderStroke(1.dp, Color.Red)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(
                "DATA QUALITY & PRIVACY",
                style = MaterialTheme.typography.labelSmall,
                color = if (isExcellent) Color(0xFF00C853) else Color.Red,
                fontWeight = FontWeight.Bold
            )
            
            if (hasDistanceIssue || hasGpsIssue) {
                report.issues.forEach { issue ->
                    // Only show issues that haven't been "silenced" by opt-out
                    val isSilenced = (issue.contains("distance") && !collectDistance) || (issue.contains("GPS") && !collectGpsRoutes)
                    if (!isSilenced) {
                        Text("⚠️ $issue", style = MaterialTheme.typography.bodySmall, color = Color.White, modifier = Modifier.padding(top = 4.dp))
                    }
                }
                
                Spacer(modifier = Modifier.height(12.dp))
                Button(
                    onClick = onOpenSourceApp,
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = Color.DarkGray)
                ) {
                    Text("CONFIGURE SOURCE APP", style = MaterialTheme.typography.labelSmall)
                }
            } else if (isExcellent && report.isExcellent) {
                Text("Status: Excellent", style = MaterialTheme.typography.bodySmall, color = Color.Gray, modifier = Modifier.padding(top = 4.dp))
            }

            Spacer(modifier = Modifier.height(12.dp))
            DataPreferenceRow("Collect Native Distance", collectDistance, onCollectDistanceChange)
            DataPreferenceRow("Collect GPS Routes", collectGpsRoutes, onCollectGpsRoutesChange)
        }
    }
}

@Composable
fun DataPreferenceRow(label: String, checked: Boolean, onCheckedChange: (Boolean) -> Unit) {
    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = Color.White)
        Switch(checked = checked, onCheckedChange = onCheckedChange, colors = SwitchDefaults.colors(checkedThumbColor = Color(0xFF00E5FF)))
    }
}

@Composable
fun PermissionCard(title: String, description: String, buttonText: String, onGrant: () -> Unit, onOpenSettings: () -> Unit, isWarning: Boolean = false) {
    Card(colors = CardDefaults.cardColors(containerColor = if (isWarning) Color(0xFF332B00) else Color(0xFF330000)), modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(title, style = MaterialTheme.typography.titleSmall, color = Color.White)
            Text(description, style = MaterialTheme.typography.bodySmall, color = Color.LightGray)
            Row(modifier = Modifier.align(Alignment.End)) {
                if (buttonText != "Settings" && buttonText != "Check Settings") {
                    TextButton(onClick = onOpenSettings) { Text("Settings", color = Color.Gray) }
                }
                Button(onClick = onGrant) { Text(buttonText) }
            }
        }
    }
}
