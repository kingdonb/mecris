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
import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
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
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.concurrent.TimeUnit
import kotlin.math.sin

class MainActivity : ComponentActivity() {

    private lateinit var pocketIdAuth: PocketIdAuth
    private lateinit var healthConnectManager: HealthConnectManager

    private val spinBaseUrl = "https://mecris-go-api-xupkwcis.fermyon.app/" 
    private val syncApi = SyncServiceApi.create(spinBaseUrl)

    private val authResultLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        pocketIdAuth.handleAuthorizationResponse(result.data)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        pocketIdAuth = PocketIdAuth(this)
        healthConnectManager = HealthConnectManager(this)

        setupWorkManager()

        val requestPermissionActivityContract = PermissionController.createRequestPermissionResultContract()
        
        val requestForegroundPermissions = registerForActivityResult(requestPermissionActivityContract) { granted ->
            Log.d("MainActivity", "Foreground Permissions Result: $granted")
            // Always recreate to trigger fresh logs from HealthConnectManager
            recreate()
        }

        val requestRoutePermission = registerForActivityResult(requestPermissionActivityContract) { granted ->
            Log.d("MainActivity", "Route Permission Result: $granted")
            recreate()
        }

        val requestBackgroundPermission = registerForActivityResult(requestPermissionActivityContract) { granted ->
            Log.d("MainActivity", "Background Permission Result: $granted")
            recreate()
        }

        setContent {
            MecrisTheme {
                MecrisDashboard(
                    auth = pocketIdAuth,
                    healthManager = healthConnectManager,
                    syncApi = syncApi,
                    authResultLauncher = authResultLauncher,
                    onRequestForeground = { 
                        Log.d("MainActivity", "Launching foreground request: ${healthConnectManager.foregroundPermissions}")
                        requestForegroundPermissions.launch(healthConnectManager.foregroundPermissions) 
                    },
                    onRequestRoute = { 
                        Log.d("MainActivity", "Launching route request: ${healthConnectManager.routePermission}")
                        requestRoutePermission.launch(setOf(healthConnectManager.routePermission)) 
                    },
                    onRequestBackground = { 
                        Log.d("MainActivity", "Launching background request: ${healthConnectManager.backgroundPermission}")
                        requestBackgroundPermission.launch(setOf(healthConnectManager.backgroundPermission)) 
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
    authResultLauncher: ActivityResultLauncher<Intent>,
    onRequestForeground: () -> Unit,
    onRequestRoute: () -> Unit,
    onRequestBackground: () -> Unit,
    onOpenSettings: () -> Unit
) {
    val authState by auth.authState.collectAsState()
    val scope = rememberCoroutineScope()
    var walkData by remember { mutableStateOf<WalkDataSummary?>(null) }
    var isLoading by remember { mutableStateOf(false) }
    var syncStatus by remember { mutableStateOf("Ready") }
    var lastSyncTime by remember { mutableStateOf("") }
    
    // UI State
    var showSystemHealth by remember { mutableStateOf(false) }
    
    // Opt-out preferences
    var collectDistance by remember { mutableStateOf(true) }
    var collectGpsRoutes by remember { mutableStateOf(true) }

    // Navigation: Handle system back press
    BackHandler(enabled = showSystemHealth) {
        showSystemHealth = false
    }

    val forceSync = {
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
                                timezone = ZoneId.systemDefault().id
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

    LaunchedEffect(Unit) {
        if (healthManager.hasForegroundPermissions()) {
            walkData = healthManager.fetchRecentWalkData()
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
                    onRequestForeground = onRequestForeground,
                    onRequestRoute = onRequestRoute,
                    onRequestBackground = onRequestBackground,
                    onOpenSettings = onOpenSettings
                )
            } else {
                MainNeuralDashboard(
                    walkData = walkData,
                    syncStatus = syncStatus,
                    lastSyncTime = lastSyncTime,
                    isLoading = isLoading,
                    collectDistance = collectDistance,
                    collectGpsRoutes = collectGpsRoutes,
                    onForceSync = { forceSync() },
                    onOpenSystemHealth = { showSystemHealth = true }
                )
            }
        }
    }
}

@Composable
fun MainNeuralDashboard(
    walkData: WalkDataSummary?,
    syncStatus: String,
    lastSyncTime: String,
    isLoading: Boolean,
    collectDistance: Boolean,
    collectGpsRoutes: Boolean,
    onForceSync: () -> Unit,
    onOpenSystemHealth: () -> Unit
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
        val momentumValue = if (hasWalked) 0.9f else 0.2f
        MomentumVisualizer(momentum = momentumValue)
        
        Column(modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 8.dp),
               horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = if (hasWalked) "STABLE" else "CRITICAL",
                style = MaterialTheme.typography.labelLarge,
                color = if (hasWalked) Color(0xFF00C853) else Color(0xFFFF1744),
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
        value = 21.00,
        label = "VIRTUAL BUDGET",
        digitColor = Color(0xFFFFD600)
    )

    Spacer(modifier = Modifier.height(8.dp))

    val miles = (walkData?.totalDistanceMeters ?: 0.0) / 1609.34
    OdometerView(
        value = miles,
        label = "TODAY'S DISTANCE",
        suffix = "MI",
        digitColor = Color(0xFF00E5FF),
        digits = 4,
        decimalPlaces = 2
    )
    
    Spacer(modifier = Modifier.height(24.dp))
    
    Text(
        text = "LANGUAGE LIABILITIES",
        style = MaterialTheme.typography.labelSmall,
        color = Color.Gray
    )
    
    Spacer(modifier = Modifier.height(8.dp))
    
    LanguageForecastCard("ARABIC", 2532, 6, Color(0xFFFFD600))
    Spacer(modifier = Modifier.height(8.dp))
    LanguageForecastCard("GREEK", 0, 46, Color(0xFF00E5FF))
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
    onRequestRoute: () -> Unit,
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
        PermissionCard(
            title = "Route Access",
            description = "High-fidelity outdoor tracking",
            buttonText = "Grant",
            onGrant = onRequestRoute,
            onOpenSettings = onOpenSettings,
            isWarning = true
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
fun MomentumVisualizer(momentum: Float) {
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

    val color1 = if (momentum > 0.5f) Color(0xFF00C853) else Color(0xFFFF1744)
    val color2 = if (momentum > 0.5f) Color(0xFF2979FF) else Color(0xFFFFEA00)

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
fun LanguageForecastCard(name: String, today: Int, tomorrow: Int, color: Color) {
    Surface(modifier = Modifier.fillMaxWidth(), color = Color(0xFF1E1E1E), shape = RoundedCornerShape(8.dp)) {
        Row(modifier = Modifier.padding(12.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Column {
                Text(name, style = MaterialTheme.typography.labelLarge, color = color, fontWeight = FontWeight.Bold)
                Text("Today: $today cards", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
            }
            Column(horizontalAlignment = Alignment.End) {
                Text("TOMORROW", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
                Text("+$tomorrow", style = MaterialTheme.typography.headlineSmall, color = Color.White, fontWeight = FontWeight.Black)
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
                TextButton(onClick = onOpenSettings) { Text("Settings", color = Color.Gray) }
                Button(onClick = onGrant) { Text(buttonText) }
            }
        }
    }
}
