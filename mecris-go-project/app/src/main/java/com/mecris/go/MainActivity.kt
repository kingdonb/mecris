package com.mecris.go

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Build
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
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.foundation.text.KeyboardOptions
import com.mecris.go.profile.ProfilePreferencesManager
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
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

        val requestNotificationPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            Log.d("MainActivity", "Notification Permission Result: $granted")
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
                    onGrantNotification = {
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                            requestNotificationPermission.launch(android.Manifest.permission.POST_NOTIFICATIONS)
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
                    },
                    onOpenNotificationSettings = {
                        val intent = Intent().apply {
                            when {
                                Build.VERSION.SDK_INT >= Build.VERSION_CODES.O -> {
                                    action = android.provider.Settings.ACTION_APP_NOTIFICATION_SETTINGS
                                    putExtra(android.provider.Settings.EXTRA_APP_PACKAGE, packageName)
                                }
                                else -> {
                                    action = android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS
                                    data = Uri.fromParts("package", packageName, null)
                                }
                            }
                        }
                        try {
                            startActivity(intent)
                        } catch (e: Exception) {
                            Log.e("MainActivity", "Failed to open notification settings: ${e.message}")
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
    onGrantNotification: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenNotificationSettings: () -> Unit
) {
    val authState by auth.authState.collectAsState()
    val scope = rememberCoroutineScope()
    val cache = remember { persistenceManager.loadDashboard() }
    val context = LocalContext.current
    
    var walkData by remember { mutableStateOf<WalkDataSummary?>(cache?.walkData) }
    var budgetAmount by remember { mutableStateOf<Double?>(cache?.budgetAmount) }
    var languageStats by remember { mutableStateOf<List<com.mecris.go.sync.LanguageStatDto>>(cache?.languageStats ?: emptyList()) }
    var aggregateStatus by remember { mutableStateOf<com.mecris.go.sync.AggregateStatusResponseDto?>(cache?.aggregateStatus) }
    var homeServerActive by remember { mutableStateOf<Boolean?>(cache?.homeServerActive) }
    var isLoading by remember { mutableStateOf(false) }
    var isFetching by remember { mutableStateOf(cache?.languageStats.isNullOrEmpty() && cache?.budgetAmount == null) }
    var surgicalUpdateInProgress by remember { mutableStateOf(false) }

    var fetchError by remember { mutableStateOf<String?>(null) }
    var syncStatus by remember { mutableStateOf("Ready") }
    var lastSyncTime by remember { mutableStateOf(cache?.lastSyncTime ?: "") }
    
    // UI State
    var showSystemHealth by remember { mutableStateOf(false) }
    var showProfileSettings by remember { mutableStateOf(false) }
    var showSovereignLab by remember { mutableStateOf(false) }
    
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
    BackHandler(enabled = showProfileSettings) {
        showProfileSettings = false
    }
    BackHandler(enabled = showSystemHealth && !showProfileSettings) {
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
            
            try {
                val token = auth.getAccessTokenSuspend()
                if (token != null) {
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
                        val walkResponse = syncApi.uploadWalk("Bearer $token", dto)
                        
                        if (walkResponse.isSuccessful) {
                            // Send heartbeat to register client presence in Neon
                            try {
                                val hbResponse = syncApi.sendHeartbeat(
                                    "Bearer $token",
                                    com.mecris.go.sync.HeartbeatRequestDto(role = "android_client", process_id = "com.mecris.go.ui")
                                )
                                if (!hbResponse.isSuccessful) {
                                    Log.w("MecrisDashboard", "Heartbeat failed: ${hbResponse.code()}")
                                }
                            } catch (e: Exception) {
                                Log.w("MecrisDashboard", "Heartbeat exception (non-fatal): ${e.message}")
                            }

                            syncStatus = "Success"
                            lastSyncTime = LocalDateTime.now().format(DateTimeFormatter.ofPattern("HH:mm"))
                        } else {
                            syncStatus = "Error: ${walkResponse.code()}"
                            Log.e("MecrisDashboard", "Sync failed with code: ${walkResponse.code()}")
                        }
                    } catch (e: Exception) {
                        syncStatus = "Error"
                        Log.e("MecrisDashboard", "Sync failed: ${e.message}")
                    } finally {
                        isLoading = false
                    }
                } else {
                    syncStatus = "Auth Required"
                    isLoading = false
                }
            } catch (e: Exception) {
                syncStatus = "Auth Error"
                isLoading = false
                Log.e("MecrisDashboard", "Auth failed during force sync: ${e.message}")
            }
        }
    }

    LaunchedEffect(refreshTrigger) {
        if (surgicalUpdateInProgress) {
            Log.d("MecrisDashboard", "Skipping full refresh: surgical update in progress")
            return@LaunchedEffect
        }
        val isStale = persistenceManager.isCacheStale()
        // Only skip if this is the initial launch AND cache is fresh
        if (refreshTrigger == 0 && !isStale) {
            Log.d("MecrisDashboard", "Initial launch with fresh cache, skipping fetch.")
            isFetching = false
            return@LaunchedEffect
        }

        Log.d("MecrisDashboard", "Refreshing walk data (Trigger: $refreshTrigger, Stale: $isStale)")
        // Only show full-screen "FETCHING..." if we have no cached data at all
        isFetching = languageStats.isEmpty() && budgetAmount == null
        isLoading = true
        if (syncStatus == "Ready" || syncStatus == "Success" || syncStatus == "Error") {
            syncStatus = "Fetching..."
        }
        fetchError = null
        walkData = healthManager.fetchRecentWalkData()
        
        try {
            val token = auth.getAccessTokenSuspend()
            if (token != null) {
                try {
                    val budgetResponse = syncApi.getBudget("Bearer $token")
                    if (budgetResponse.isSuccessful) {
                        budgetAmount = budgetResponse.body()?.remaining_budget
                    }

                    val healthResponse = syncApi.getHealth("Bearer $token")
                    if (healthResponse.isSuccessful) {
                        homeServerActive = healthResponse.body()?.home_server_active == true
                    }

                    val aggregateResponse = syncApi.getAggregateStatus("Bearer $token")
                    if (aggregateResponse.isSuccessful) {
                        aggregateStatus = aggregateResponse.body()
                    }
                    
                    // 1. QUICK FETCH: Get currently known languages first
                    var langResponse = syncApi.getLanguages("Bearer $token")
                    if (langResponse.isSuccessful && !surgicalUpdateInProgress) {
                        languageStats = langResponse.body()?.languages ?: emptyList()
                    }
                    
                    // We have DB data, so release the UI block immediately
                    isFetching = false

                    // 2. SLOW SYNC: Proactively trigger cloud sync (Spin will skip if Home is active)
                    try {
                        val syncResponse = syncApi.triggerCloudSync("Bearer $token")
                        if (!syncResponse.isSuccessful) {
                            throw retrofit2.HttpException(syncResponse)
                        }
                        
                        // 3. FRESH FETCH: Grab the updated stats after the sync completes
                        langResponse = syncApi.getLanguages("Bearer $token")
                        if (langResponse.isSuccessful && !surgicalUpdateInProgress) {
                            languageStats = langResponse.body()?.languages ?: emptyList()
                        }
                        
                        val freshAggregateResponse = syncApi.getAggregateStatus("Bearer $token")
                        if (freshAggregateResponse.isSuccessful) {
                            aggregateStatus = freshAggregateResponse.body()
                        }
                    } catch (se: retrofit2.HttpException) {
                        val errorBody = se.response()?.errorBody()?.string()
                        val detail = try {
                            com.google.gson.Gson().fromJson(errorBody, com.mecris.go.sync.SyncResponse::class.java).message
                        } catch (e: Exception) {
                            errorBody ?: se.message()
                        }
                        Log.e("MecrisDashboard", "Cloud sync trigger failed ($detail)")
                        fetchError = "Sync Failed: $detail"
                        syncStatus = "Error"
                    } catch (se: Exception) {
                        Log.e("MecrisDashboard", "Cloud sync trigger skipped/failed: ${se.message}")
                        fetchError = "Sync Error: ${se.message}"
                        syncStatus = "Error"
                    }

                    // Save to cache
                    val now = LocalDateTime.now().format(DateTimeFormatter.ofPattern("HH:mm"))
                    lastSyncTime = now
                    persistenceManager.saveDashboard(DashboardCache(
                        walkData = walkData,
                        budgetAmount = budgetAmount,
                        languageStats = languageStats,
                        aggregateStatus = aggregateStatus,
                        homeServerActive = homeServerActive,
                        lastSyncTime = now
                    ))
                    if (syncStatus == "Fetching...") syncStatus = "Success"
                } catch (e: HttpException) {
                    val errorBody = e.response()?.errorBody()?.string()
                    val detail = try {
                        Gson().fromJson(errorBody, SyncResponse::class.java).message
                    } catch (ex: Exception) {
                        errorBody ?: e.message()
                    }
                    Log.e("MecrisDashboard", "Failed to fetch remote data: $detail")
                    fetchError = detail
                    syncStatus = "Error"
                } catch (e: Exception) {
                    Log.e("MecrisDashboard", "Failed to fetch remote data: ${e.message}")
                    fetchError = e.message ?: "Unknown error"
                    syncStatus = "Error"
                } finally {
                    isFetching = false
                    isLoading = false
                }
            } else {
                isFetching = false
                isLoading = false
                syncStatus = if (authState is AuthState.Authenticated) "Network Error" else "Auth Required"
            }
        } catch (e: Exception) {
            Log.e("MecrisDashboard", "Auth refresh failed: ${e.message}")
            isFetching = false
            isLoading = false
            syncStatus = "Auth Error"
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { 
                    Text(
                        "MECRIS NEURAL LINK", 
                        letterSpacing = 1.sp, 
                        fontWeight = FontWeight.Black,
                        maxLines = 1,
                        overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis,
                        style = MaterialTheme.typography.titleMedium
                    ) 
                },
                actions = {
                    IconButton(onClick = {
                        showSovereignLab = !showSovereignLab
                        if (showSovereignLab) {
                            showProfileSettings = false
                            showSystemHealth = false
                        }
                    }) {
                        Icon(
                            imageVector = Icons.Default.Face, // Using Face as a Brain-ish proxy for now
                            contentDescription = "Sovereign Lab",
                            tint = if (showSovereignLab) Color(0xFF00E5FF) else Color.White
                        )
                    }
                    IconButton(onClick = {
                        showProfileSettings = !showProfileSettings
                        if (showProfileSettings) {
                            showSystemHealth = false
                            showSovereignLab = false
                        }
                    }) {
                        Icon(Icons.Default.Person, contentDescription = "Profile Settings")
                    }
                    IconButton(onClick = {
                        showSystemHealth = !showSystemHealth
                        if (showSystemHealth) {
                            showProfileSettings = false
                            showSovereignLab = false
                        }
                    }) {
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
            if (showProfileSettings) {
                ProfileSettingsScreen(context = context, onLogOut = {
                    auth.signOut()
                    showProfileSettings = false
                })
            } else if (showSovereignLab) {
                SovereignLabScreen(
                    context = context,
                    syncApi = syncApi,
                    walkData = walkData,
                    aggregateStatus = aggregateStatus,
                    auth = auth
                )
            } else if (showSystemHealth) {
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
                    onGrantNotification = onGrantNotification,
                    onOpenSettings = onOpenSettings,
                    onOpenNotificationSettings = onOpenNotificationSettings
                )
            } else {
                MainNeuralDashboard(
                    walkData = walkData,
                    budgetAmount = budgetAmount,
                    languageStats = languageStats,
                    aggregateStatus = aggregateStatus,
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
                    surgicalUpdateInProgress = surgicalUpdateInProgress,
                    onMultiplierChange = { name, multiplier ->
                        val oldStats = languageStats
                        // 1. Optimistic UI update
                        languageStats = languageStats.map {
                            if (it.name.equals(name, ignoreCase = true)) {
                                it.copy(pump_multiplier = multiplier)
                            } else it
                        }
                        
                        scope.launch {
                            surgicalUpdateInProgress = true
                            try {
                                val token = auth.getAccessTokenSuspend()
                                if (token != null) {
                                    val response = syncApi.updateMultiplier(
                                        "Bearer $token",
                                        com.mecris.go.sync.MultiplierRequestDto(name, multiplier)
                                    )
                                    if (!response.isSuccessful) {
                                        val errorBody = response.errorBody()?.string()
                                        val detail = try {
                                            Gson().fromJson(errorBody, SyncResponse::class.java).message
                                        } catch (e: Exception) {
                                            errorBody ?: "Code ${response.code()}"
                                        }
                                        throw Exception(detail)
                                    }
                                    
                                    // Save the optimistic state to cache on success
                                    persistenceManager.saveDashboard(DashboardCache(
                                        walkData = walkData,
                                        budgetAmount = budgetAmount,
                                        languageStats = languageStats,
                                        aggregateStatus = aggregateStatus,
                                        homeServerActive = homeServerActive,
                                        lastSyncTime = lastSyncTime
                                    ))
                                    
                                    // Give the backend a moment to settle
                                    kotlinx.coroutines.delay(2000)
                                    // Trigger refresh
                                    onRefreshRequested()
                                } else {
                                    Toast.makeText(context, "Authentication required", Toast.LENGTH_SHORT).show()
                                    languageStats = oldStats
                                }
                            } catch (e: Exception) {
                                Log.e("MecrisApp", "Failed to update multiplier: ${e.message}")
                                Toast.makeText(context, "Link failure: ${e.message}", Toast.LENGTH_SHORT).show()
                                // 2. Revert on failure
                                languageStats = oldStats
                            } finally {
                                surgicalUpdateInProgress = false
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
    aggregateStatus: com.mecris.go.sync.AggregateStatusResponseDto?,
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
    surgicalUpdateInProgress: Boolean,
    onMultiplierChange: (String, Double) -> Unit
) {
    MajestyCakeWidget(status = aggregateStatus)

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
        val hasSteps = (walkData?.totalSteps ?: 0L) >= 2000
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
            val statusLabel = if (homeServerActive!!) "HOME: ONLINE" else "CLOUD: AUTONOMOUS"
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
        languageStats.sortedBy { if (it.has_goal) it.safebuf else 999 }.forEach { stat ->
            ReviewPumpWidget(
                stat = stat,
                surgicalUpdateInProgress = surgicalUpdateInProgress,
                onMultiplierChange = onMultiplierChange
            )
            Spacer(modifier = Modifier.height(16.dp))
        }
    }
}

@Composable
fun ReviewPumpWidget(
    stat: com.mecris.go.sync.LanguageStatDto,
    surgicalUpdateInProgress: Boolean,
    onMultiplierChange: (String, Double) -> Unit
) {
    // 1. OPTIMISTIC STATE: We keep a local copy of the multiplier so the UI reacts instantly
    var localMultiplier by remember(stat.name, stat.pump_multiplier) { 
        mutableStateOf(stat.pump_multiplier ?: 1.0) 
    }
    
    val currentDisplayMultiplier = if (surgicalUpdateInProgress) localMultiplier else (stat.pump_multiplier ?: 1.0)
    val leverName = com.mecris.go.sync.ReviewPumpCalculator.getLeverName(currentDisplayMultiplier)
    val targetFlowRate = com.mecris.go.sync.ReviewPumpCalculator.calculateTargetFlowRate(currentDisplayMultiplier, stat.current, stat.tomorrow)
    
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
                    listOf(1, 2, 3, 4, 5, 6, 7, 10).forEach { i ->
                        val isSelected = currentDisplayMultiplier.toInt() == i
                        Box(
                            modifier = Modifier
                                .padding(horizontal = 4.dp)
                                .size(32.dp) // Larger tap target
                                .background(
                                    if (isSelected) accentColor else Color(0xFF333333),
                                    RoundedCornerShape(6.dp)
                                )
                                .clickable(enabled = !surgicalUpdateInProgress) { 
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
    onGrantNotification: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenNotificationSettings: () -> Unit
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
        is AuthState.Idle -> {
            IntegrationCard(
                name = "POCKET ID",
                status = "Disconnected",
                description = "Login required for cloud sync"
            )
            Spacer(modifier = Modifier.height(8.dp))
            Button(onClick = { auth.authenticateWithPasskey(authResultLauncher) }, modifier = Modifier.fillMaxWidth()) {
                Text("Sign In with Pocket ID")
            }
        }
        is AuthState.Error -> {
            IntegrationCard(
                name = "POCKET ID",
                status = if (state.isPermanent) "Auth Failed" else "Network Unavailable",
                description = state.message
            )
            if (state.isPermanent) {
                Spacer(modifier = Modifier.height(8.dp))
                Button(onClick = { auth.authenticateWithPasskey(authResultLauncher) }, modifier = Modifier.fillMaxWidth()) {
                    Text("Sign In with Pocket ID")
                }
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
    var hasNotification by remember { mutableStateOf(true) }

    val context = LocalContext.current

    LaunchedEffect(Unit) {
        hasForeground = healthManager.hasForegroundPermissions()
        hasRoute = healthManager.hasRoutePermission()
        hasBackground = healthManager.hasBackgroundPermission()
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            hasNotification = androidx.core.content.ContextCompat.checkSelfPermission(
                context, android.Manifest.permission.POST_NOTIFICATIONS
            ) == android.content.pm.PackageManager.PERMISSION_GRANTED
        }
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

    Spacer(modifier = Modifier.height(8.dp))

    if (!hasNotification && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        PermissionCard(
            title = "Notification Access",
            description = "Arabic Pressure & Urgent Nag system",
            buttonText = "Grant",
            onGrant = onGrantNotification,
            onOpenSettings = onOpenNotificationSettings,
            isWarning = true
        )
    } else {
        IntegrationCard("NAG ENGINE", "Armed", "Sovereign local notifications enabled")
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

@Composable
fun MajestyCakeWidget(status: com.mecris.go.sync.AggregateStatusResponseDto?) {
    if (status == null) return

    val infiniteTransition = rememberInfiniteTransition(label = "majesty")
    val glowAlpha by infiniteTransition.animateFloat(
        initialValue = 0.3f,
        targetValue = 0.8f,
        animationSpec = infiniteRepeatable(
            animation = tween(1500, easing = LinearOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "glow"
    )

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(bottom = 16.dp),
        color = Color(0xFF121212),
        shape = RoundedCornerShape(16.dp),
        border = if (status.all_clear) 
            androidx.compose.foundation.BorderStroke(2.dp, Color(0xFFFFD600).copy(alpha = glowAlpha))
            else null
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            if (status.all_clear) {
                Text(
                    text = "✨ THE MAJESTY CAKE ✨",
                    style = MaterialTheme.typography.titleMedium,
                    color = Color(0xFFFFD600),
                    fontWeight = FontWeight.Black,
                    letterSpacing = 2.sp
                )
                Spacer(modifier = Modifier.height(8.dp))
                // Majestic Cake Emoji with Glow
                Box(contentAlignment = Alignment.Center) {
                    Canvas(modifier = Modifier.size(80.dp)) {
                        drawCircle(
                            brush = Brush.radialGradient(
                                colors = listOf(Color(0xFFFFD600).copy(alpha = 0.4f), Color.Transparent),
                                center = center,
                                radius = size.minDimension / 1.5f
                            ),
                            radius = size.minDimension / 1.5f * glowAlpha
                        )
                    }
                    Text("🍰", fontSize = 48.sp)
                }
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "ALL GOALS SATISFIED",
                    style = MaterialTheme.typography.labelSmall,
                    color = Color.White,
                    fontWeight = FontWeight.Bold
                )
            } else {
                Text(
                    text = "DAILY ACCOUNTABILITY",
                    style = MaterialTheme.typography.labelSmall,
                    color = Color.Gray,
                    letterSpacing = 1.sp
                )
                Spacer(modifier = Modifier.height(12.dp))
                
                // Progress Counter
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = status.score,
                        style = MaterialTheme.typography.headlineMedium,
                        color = Color.White,
                        fontWeight = FontWeight.Black
                    )
                    Spacer(modifier = Modifier.width(16.dp))
                    
                    // Mini icons
                    GoalStatusIcon(label = "🚶", met = status.components.walk)
                    Spacer(modifier = Modifier.width(8.dp))
                    GoalStatusIcon(label = "🇦", met = status.components.arabic)
                    Spacer(modifier = Modifier.width(8.dp))
                    GoalStatusIcon(label = "🇬", met = status.components.greek)
                }
            }
        }
    }
}

@Composable
fun GoalStatusIcon(label: String, met: Boolean) {
    Surface(
        color = if (met) Color(0xFF004D40) else Color(0xFF333333),
        shape = RoundedCornerShape(4.dp),
        border = if (met) androidx.compose.foundation.BorderStroke(1.dp, Color(0xFF00C853)) else null
    ) {
        Box(modifier = Modifier.padding(4.dp), contentAlignment = Alignment.Center) {
            Text(
                text = label, 
                fontSize = 14.sp,
                modifier = Modifier.alpha(if (met) 1f else 0.4f)
            )
        }
    }
}

@Composable
fun ProfileSettingsScreen(context: android.content.Context, onLogOut: () -> Unit) {
    val manager = remember { ProfilePreferencesManager(context) }
    val scope = rememberCoroutineScope()

    var preferredSource by remember { mutableStateOf(manager.getPreferredHealthSource() ?: "") }
    var phoneNumber by remember { mutableStateOf(manager.getPhoneNumber() ?: "") }
    var beeminderUser by remember { mutableStateOf(manager.getBeeminderUser() ?: "") }
    var latitude by remember { mutableStateOf(manager.getLatitude() ?: "") }
    var longitude by remember { mutableStateOf(manager.getLongitude() ?: "") }
    var vacationUntil by remember { mutableStateOf(manager.getVacationModeUntil() ?: "") }
    var autoSync by remember { mutableStateOf(manager.isAutonomousSyncEnabled()) }
    var saveStatus by remember { mutableStateOf("") }

    Column {
        Text(
            text = "PROFILE SETTINGS",
            style = MaterialTheme.typography.titleMedium,
            color = Color.White,
            fontWeight = FontWeight.Bold
        )
        Spacer(modifier = Modifier.height(16.dp))

        Text("Sovereign Identity", color = Color.Gray, style = MaterialTheme.typography.labelSmall)
        OutlinedTextField(
            value = phoneNumber,
            onValueChange = { phoneNumber = it },
            label = { Text("Phone Number (E.164)") },
            placeholder = { Text("+15551234567") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )
        Spacer(modifier = Modifier.height(8.dp))
        OutlinedTextField(
            value = beeminderUser,
            onValueChange = { beeminderUser = it },
            label = { Text("Beeminder Username") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )

        Spacer(modifier = Modifier.height(16.dp))
        Text("Oracle Location (Solar/Weather)", color = Color.Gray, style = MaterialTheme.typography.labelSmall)
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = latitude,
                onValueChange = { latitude = it },
                label = { Text("Lat") },
                modifier = Modifier.weight(1f),
                singleLine = true
            )
            OutlinedTextField(
                value = longitude,
                onValueChange = { longitude = it },
                label = { Text("Lon") },
                modifier = Modifier.weight(1f),
                singleLine = true
            )
        }
        if (latitude.isNotEmpty() && longitude.isNotEmpty()) {
            TextButton(onClick = {
                val intent = Intent(Intent.ACTION_VIEW, Uri.parse("geo:$latitude,$longitude?q=$latitude,$longitude(Oracle+Location)"))
                context.startActivity(intent)
            }) {
                Text("VIEW ON MAPS 🗺️", color = Color(0xFF42A5F5))
            }
        }

        Spacer(modifier = Modifier.height(16.dp))
        Text("Narrative Sensitivity", color = Color.Gray, style = MaterialTheme.typography.labelSmall)
        OutlinedTextField(
            value = vacationUntil,
            onValueChange = { vacationUntil = it },
            label = { Text("Vacation Mode Until (ISO)") },
            placeholder = { Text("YYYY-MM-DD") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )
        Text("Boarding mode: suppresses Boris/Fiona references.", style = MaterialTheme.typography.bodySmall, color = Color.Gray)

        Spacer(modifier = Modifier.height(16.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            androidx.compose.material3.Switch(
                checked = autoSync,
                onCheckedChange = { autoSync = it }
            )
            Spacer(modifier = Modifier.width(8.dp))
            Column {
                Text("Autonomous Sync Consent", color = Color.White)
                Text("Allow cloud crons to sync on your behalf.", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
            }
        }

        Spacer(modifier = Modifier.height(24.dp))
        Button(
            onClick = {
                manager.setPreferredHealthSource(preferredSource)
                manager.setPhoneNumber(phoneNumber)
                manager.setBeeminderUser(beeminderUser)
                manager.setLatitude(latitude)
                manager.setLongitude(longitude)
                manager.setVacationModeUntil(vacationUntil)
                manager.setAutonomousSyncEnabled(autoSync)
                saveStatus = "Saved locally"
            },
            modifier = Modifier.fillMaxWidth(),
            colors = androidx.compose.material3.ButtonDefaults.buttonColors(containerColor = Color(0xFF1B5E20))
        ) {
            Text("SAVE SETTINGS")
        }
        
        Spacer(modifier = Modifier.height(8.dp))
        OutlinedButton(
            onClick = {
                manager.clearAll()
                PocketIdAuth(context).signOut()
                (context as? ComponentActivity)?.finish()
            },
            modifier = Modifier.fillMaxWidth(),
            colors = androidx.compose.material3.ButtonDefaults.outlinedButtonColors(contentColor = Color.Red)
        ) {
            Text("LOGOUT & CLEAR CACHE")
        }

        if (saveStatus.isNotEmpty()) {
            Spacer(modifier = Modifier.height(8.dp))
            Text(saveStatus, color = Color(0xFF00C853), modifier = Modifier.align(Alignment.CenterHorizontally))
        }
    }

    Spacer(modifier = Modifier.height(32.dp))
    Button(
        onClick = onLogOut,
        modifier = Modifier.fillMaxWidth(),
        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF6B0000))
    ) {
        Text("LOG OUT")
    }
}

@Composable
fun SovereignLabScreen(
    context: android.content.Context,
    syncApi: SyncServiceApi,
    walkData: WalkDataSummary?,
    aggregateStatus: com.mecris.go.sync.AggregateStatusResponseDto?,
    auth: PocketIdAuth
) {
    val scope = rememberCoroutineScope()
    val manager = remember { ProfilePreferencesManager(context) }
    val brain = remember { com.mecris.go.ai.SovereignBrain(context) }
    
    var weatherData by remember { mutableStateOf<com.mecris.go.sync.WeatherHeuristicResponseDto?>(null) }
    var narrativeResult by remember { mutableStateOf<com.mecris.go.ai.SovereignBrain.NarrativeResult?>(null) }
    var isThinking by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
        Text(
            text = "SOVEREIGN BRAIN LAB 🧪",
            style = MaterialTheme.typography.titleMedium,
            color = Color.White,
            fontWeight = FontWeight.Bold
        )
        Spacer(modifier = Modifier.height(16.dp))

        // 1. Current Stats Block
        Text("RAW INPUT CONTEXT", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
        Spacer(modifier = Modifier.height(8.dp))
        Card(
            colors = CardDefaults.cardColors(containerColor = Color(0xFF1A1A1B)),
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(modifier = Modifier.padding(12.dp)) {
                Text("Steps: ${walkData?.step_count ?: 0} / 2000", color = Color.White)
                Text("Arabic: ${if (aggregateStatus?.components?.arabic == true) "✅ DONE" else "❌ DEBT"}", color = Color.White)
                Text("Greek: ${if (aggregateStatus?.components?.greek == true) "✅ DONE" else "❌ DEBT"}", color = Color.White)
                Text("Vacation Mode: ${aggregateStatus?.vacation_mode_until ?: "None"}", color = Color.White)
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // 2. Weather Oracle Block
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("WEATHER ORACLE", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
            Spacer(modifier = Modifier.weight(1f))
            TextButton(onClick = {
                scope.launch {
                    val lat = manager.getLatitude()?.toDoubleOrNull() ?: 40.7128
                    val lon = manager.getLongitude()?.toDoubleOrNull() ?: -74.0060
                    try {
                        val resp = syncApi.getWeatherHeuristic(lat, lon)
                        if (resp.isSuccessful) weatherData = resp.body()
                        else error = "Weather FAILED: ${resp.code()}"
                    } catch (e: Exception) {
                        error = e.message
                    }
                }
            }) {
                Text("REFETCH", color = Color(0xFF00E5FF))
            }
        }
        Card(
            colors = CardDefaults.cardColors(containerColor = Color(0xFF1A1A1B)),
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(modifier = Modifier.padding(12.dp)) {
                if (weatherData != null) {
                    Text("Condition: ${weatherData!!.conditions} (${weatherData!!.description})", color = Color.White)
                    Text("Temp: ${weatherData!!.temperature}°C", color = Color.White)
                    Text("Dark: ${weatherData!!.is_dark}", color = Color.White)
                    Text("Safe to Walk: ${weatherData!!.is_walk_appropriate}", color = Color.White)
                } else {
                    Text("No weather data loaded.", color = Color.DarkGray)
                }
            }
        }

        Spacer(modifier = Modifier.height(24.dp))

        // 3. LLM Interaction Block
        Text("LLM BRAIN (GEMMA-2B)", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
        Spacer(modifier = Modifier.height(8.dp))
        Button(
            onClick = {
                scope.launch {
                    isThinking = true
                    error = null
                    try {
                        val isSensitive = aggregateStatus?.vacation_mode_until != null
                        val target = if (aggregateStatus?.components?.arabic == false) "ARABIC" 
                                     else if (aggregateStatus?.components?.walk == false) "WALK"
                                     else "GREEK"
                        
                        narrativeResult = brain.generateWithContext(
                            targetGoal = target,
                            isSensitive = isSensitive,
                            weatherConditions = weatherData?.conditions,
                            isDark = weatherData?.is_dark ?: false
                        )
                        if (narrativeResult == null) error = "Model not found on device!"
                    } catch (e: Exception) {
                        error = e.message
                    } finally {
                        isThinking = false
                    }
                }
            },
            enabled = !isThinking,
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF00E5FF), contentColor = Color.Black)
        ) {
            Text(if (isThinking) "THINKING..." else "EXECUTE INFERENCE")
        }

        if (error != null) {
            Text(error!!, color = Color.Red, style = MaterialTheme.typography.bodySmall)
        }

        if (narrativeResult != null) {
            Spacer(modifier = Modifier.height(16.dp))
            Text("LLM OUTPUT", color = Color(0xFF00C853), style = MaterialTheme.typography.labelSmall)
            Text(
                text = narrativeResult!!.nag,
                style = MaterialTheme.typography.bodyLarge,
                color = Color.White,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(vertical = 8.dp)
            )
            
            Spacer(modifier = Modifier.height(16.dp))
            Text("RAW PROMPT SENT TO GEMMA", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
            Card(
                colors = CardDefaults.cardColors(containerColor = Color.Black),
                border = androidx.compose.foundation.BorderStroke(1.dp, Color.DarkGray),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    text = narrativeResult!!.prompt,
                    color = Color(0xFF00C853),
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(12.dp),
                    fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace
                )
            }
        }
        
        Spacer(modifier = Modifier.height(32.dp))
    }
}
