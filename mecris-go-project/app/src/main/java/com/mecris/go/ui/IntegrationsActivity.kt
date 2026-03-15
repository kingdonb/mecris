package com.mecris.go.ui

import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.mecris.go.auth.PocketIdAuth
import com.mecris.go.auth.AuthState
import com.mecris.go.health.HealthConnectManager
import com.mecris.go.health.WalkDataSummary
import com.mecris.go.sync.SyncServiceApi
import com.mecris.go.sync.WalkDataSummaryDto
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

class IntegrationsActivity : ComponentActivity() {
    private lateinit var healthConnectManager: HealthConnectManager
    private lateinit var pocketIdAuth: PocketIdAuth

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        healthConnectManager = HealthConnectManager(this)
        pocketIdAuth = PocketIdAuth(this)
        
        setContent {
            MaterialTheme(
                colorScheme = darkColorScheme(
                    primary = Color(0xFF00E5FF),
                    secondary = Color(0xFF00C853),
                    background = Color(0xFF121212),
                    surface = Color(0xFF1E1E1E)
                )
            ) {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    IntegrationsScreen(
                        healthManager = healthConnectManager,
                        pocketIdAuth = pocketIdAuth,
                        onBack = { finish() }
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun IntegrationsScreen(
    healthManager: HealthConnectManager, 
    pocketIdAuth: PocketIdAuth,
    onBack: () -> Unit
) {
    var walkData by remember { mutableStateOf<WalkDataSummary?>(null) }
    var lastSyncTime by remember { mutableStateOf("") }
    var syncStatus by remember { mutableStateOf("Ready") }
    var isLoading by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    
    val spinBaseUrl = "https://mecris-go-api-xupkwcis.fermyon.app/"
    val syncApi = SyncServiceApi.create(spinBaseUrl)

    val forceSync = {
        scope.launch {
            isLoading = true
            syncStatus = "Syncing..."
            
            val currentWalk = healthManager.fetchRecentWalkData()
            walkData = currentWalk
            
            pocketIdAuth.getValidAccessToken { token ->
                if (token != null) {
                    scope.launch {
                        try {
                            val dto = WalkDataSummaryDto(
                                start_time = currentWalk.startTime.toString(),
                                end_time = Instant.now().toString(),
                                step_count = currentWalk.totalSteps.toInt(),
                                distance_meters = currentWalk.totalDistanceMeters,
                                distance_source = currentWalk.distanceSource,
                                confidence_score = 0.9,
                                gps_route_points = currentWalk.routePointCount,
                                timezone = ZoneId.systemDefault().id
                            )
                            syncApi.uploadWalk("Bearer $token", dto)
                            syncStatus = "Success"
                            lastSyncTime = LocalDateTime.now().format(DateTimeFormatter.ofPattern("HH:mm"))
                        } catch (e: Exception) {
                            syncStatus = "Error"
                            Log.e("IntegrationsActivity", "Force sync failed: ${e.message}")
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
                title = { Text("NEURAL LINK", letterSpacing = 4.sp, fontWeight = FontWeight.Black) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
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
            Text(
                text = "SYSTEM MOMENTUM",
                style = MaterialTheme.typography.labelSmall,
                color = Color.Gray
            )
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(180.dp)
            ) {
                // Determine momentum based on walk status
                val hasWalked = walkData?.isWalkInferred == true
                val momentumValue = if (hasWalked) 0.9f else 0.3f
                MomentumVisualizer(momentum = momentumValue)
                
                // Add a small status label inside the orb area
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
                    onClick = { forceSync() },
                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 0.dp),
                    modifier = Modifier.height(32.dp),
                    enabled = !isLoading
                ) {
                    Text(if (isLoading) "SYNCING..." else "FORCE SYNC", 
                         style = MaterialTheme.typography.labelSmall, 
                         color = Color(0xFF00E5FF))
                }
            }
            
            Spacer(modifier = Modifier.height(16.dp))
            
            OdometerView(
                value = 21.00,
                label = "VIRTUAL BUDGET",
                symbol = "$",
                symbolColor = Color(0xFFFFD600), // Gold
                digitColor = Color(0xFFFFD600)  // Gold
            )

            Spacer(modifier = Modifier.height(8.dp))

            val miles = (walkData?.totalDistanceMeters ?: 0.0) / 1609.34
            OdometerView(
                value = miles,
                label = "TODAY'S DISTANCE",
                symbol = "",
                suffix = "MI",
                symbolColor = Color(0xFF00E5FF), // Cyan
                digitColor = Color(0xFF00E5FF),  // Cyan
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

            Spacer(modifier = Modifier.height(24.dp))
            
            IntegrationCard(
                name = "BEEMINDER",
                status = "Connected",
                description = "Accountability logic active"
            )
            
            Spacer(modifier = Modifier.height(12.dp))
            
            IntegrationCard(
                name = "NEON CLOUD",
                status = "Sync Active",
                description = "PostgreSQL Source of Truth"
            )
            
            Spacer(modifier = Modifier.height(12.dp))
            
            IntegrationCard(
                name = "POCKET ID",
                status = "Authenticated",
                description = "Identity & Access Management"
            )
        }
    }
}

@Composable
fun LanguageForecastCard(name: String, today: Int, tomorrow: Int, color: Color) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = Color(0xFF1E1E1E),
        shape = androidx.compose.foundation.shape.RoundedCornerShape(8.dp)
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
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
fun IntegrationCard(name: String, status: String, description: String) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = Color(0xFF1E1E1E),
        shape = androidx.compose.foundation.shape.RoundedCornerShape(8.dp)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = name,
                    style = MaterialTheme.typography.titleSmall,
                    color = Color.White,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = status,
                    style = MaterialTheme.typography.labelSmall,
                    color = Color(0xFF00C853)
                )
            }
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = description,
                style = MaterialTheme.typography.bodySmall,
                color = Color.LightGray
            )
        }
    }
}
