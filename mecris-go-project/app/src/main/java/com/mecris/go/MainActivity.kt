package com.mecris.go

import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.PermissionController
import androidx.lifecycle.lifecycleScope
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.mecris.go.auth.AuthState
import com.mecris.go.auth.PocketIdAuth
import com.mecris.go.beeminder.BeeminderApi
import com.mecris.go.health.HealthConnectManager
import com.mecris.go.health.WalkDataSummary
import com.mecris.go.health.WalkHeuristicsWorker
import kotlinx.coroutines.launch
import java.util.UUID
import java.util.concurrent.TimeUnit


class MainActivity : ComponentActivity() {

    private lateinit var pocketIdAuth: PocketIdAuth
    private lateinit var healthConnectManager: HealthConnectManager
    private val beeminderApi = BeeminderApi.create()

    // Temporary Beeminder config for Phase 1 (Ideally from Pocket ID JWT or preferences)
    private val beeminderUser = "YOUR_USERNAME"
    private val beeminderGoal = "bike"
    private val beeminderToken = "YOUR_AUTH_TOKEN" // DANGER: Keep secure in reality

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        pocketIdAuth = PocketIdAuth(this)
        healthConnectManager = HealthConnectManager(this)

        // Setup WorkManager for background polling
        setupWorkManager()

        val requestPermissionActivityContract = PermissionController.createRequestPermissionResultContract()
        
        // Launcher for Background permission
        val requestBackgroundPermission = registerForActivityResult(requestPermissionActivityContract) { granted ->
            if (granted.contains(healthConnectManager.backgroundPermission)) {
                Toast.makeText(this, "Background access granted!", Toast.LENGTH_SHORT).show()
                recreate()
            }
        }

        // Launcher for Route permission
        val requestRoutePermission = registerForActivityResult(requestPermissionActivityContract) { granted ->
            if (granted.contains(healthConnectManager.routePermission)) {
                Toast.makeText(this, "Route access granted!", Toast.LENGTH_SHORT).show()
                recreate()
            }
        }

        // Launcher for Foreground permissions
        val requestForegroundPermissions = registerForActivityResult(requestPermissionActivityContract) { granted ->
            if (granted.containsAll(healthConnectManager.foregroundPermissions)) {
                Toast.makeText(this, "Foreground permissions granted", Toast.LENGTH_SHORT).show()
                recreate()
            } else {
                recreate()
            }
        }

        setContent {
            MaterialTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    MecrisGoApp(
                        auth = pocketIdAuth,
                        healthManager = healthConnectManager,
                        onRequestForegroundPermissions = {
                            requestForegroundPermissions.launch(healthConnectManager.foregroundPermissions)
                        },
                        onRequestRoutePermission = {
                            requestRoutePermission.launch(setOf(healthConnectManager.routePermission))
                        },
                        onRequestBackgroundPermission = {
                            requestBackgroundPermission.launch(setOf(healthConnectManager.backgroundPermission))
                        },
                        onOpenSettings = {
                            val intent = Intent(HealthConnectClient.ACTION_HEALTH_CONNECT_SETTINGS)
                            startActivity(intent)
                        },
                        onLogWalk = { value ->
                            logWalkToBeeminder(value)
                        }
                    )
                }
            }
        }
    }

    private fun setupWorkManager() {
        val walkCheckRequest = PeriodicWorkRequestBuilder<WalkHeuristicsWorker>(
            15, TimeUnit.MINUTES
        ).build()

        WorkManager.getInstance(this).enqueue(walkCheckRequest)
    }

    private fun logWalkToBeeminder(value: Double) {
        lifecycleScope.launch {
            try {
                val requestId = UUID.randomUUID().toString()
                beeminderApi.createDatapoint(
                    user = beeminderUser,
                    goal = beeminderGoal,
                    authToken = beeminderToken,
                    value = value,
                    comment = "Logged directly from Mecris-Go Phase 1",
                    requestId = requestId
                )
                Toast.makeText(this@MainActivity, "Walk Logged Successfully!", Toast.LENGTH_SHORT).show()
            } catch (e: Exception) {
                Toast.makeText(this@MainActivity, "Failed to log walk: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }
}

@Composable
fun MecrisGoApp(
    auth: PocketIdAuth,
    healthManager: HealthConnectManager,
    onRequestForegroundPermissions: () -> Unit,
    onRequestRoutePermission: () -> Unit,
    onRequestBackgroundPermission: () -> Unit,
    onOpenSettings: () -> Unit,
    onLogWalk: (Double) -> Unit
) {
    val scope = rememberCoroutineScope()
    var walkData by remember { mutableStateOf<WalkDataSummary?>(null) }
    var hasForeground by remember { mutableStateOf(false) }
    var hasRoute by remember { mutableStateOf(false) }
    var hasBackground by remember { mutableStateOf(false) }
    var isLoading by remember { mutableStateOf(true) }

    // Check permissions and fetch data on load
    LaunchedEffect(Unit) {
        isLoading = true
        hasForeground = healthManager.hasForegroundPermissions()
        hasRoute = healthManager.hasRoutePermission()
        hasBackground = healthManager.hasBackgroundPermission()
        if (hasForeground) {
            walkData = healthManager.fetchRecentWalkData()
        }
        isLoading = false
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text("Mecris-Go", style = MaterialTheme.typography.headlineLarge)
        Spacer(modifier = Modifier.height(16.dp))

        // FORCED AUTH FOR PHASE 1 TESTING
        Text("✅ Authenticated (Local Mode)", 
             color = MaterialTheme.colorScheme.primary,
             style = MaterialTheme.typography.labelLarge)
        
        Spacer(modifier = Modifier.height(32.dp))

        if (isLoading) {
            CircularProgressIndicator()
        } else if (!hasForeground) {
            PermissionCard(
                title = "Foreground Permissions Missing",
                description = "Mecris-Go needs access to your steps, distance, and exercise sessions to track your walks. If the grant button does nothing, use the settings button.",
                buttonText = "Grant Foreground Access",
                onGrant = onRequestForegroundPermissions,
                onOpenSettings = onOpenSettings
            )
        } else {
            // Foreground granted, check route and background
            Column {
                if (!hasRoute) {
                    PermissionCard(
                        title = "Route Access Missing",
                        description = "To verify outdoor walks, Mecris-Go needs exercise route access.",
                        buttonText = "Grant Route Access",
                        onGrant = onRequestRoutePermission,
                        onOpenSettings = onOpenSettings,
                        isWarning = true
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                }
                
                if (!hasBackground) {
                    PermissionCard(
                        title = "Background Access Missing",
                        description = "To automatically detect walks while your phone is in your pocket, Mecris-Go needs background health access.",
                        buttonText = "Grant Background Access",
                        onGrant = onRequestBackgroundPermission,
                        onOpenSettings = onOpenSettings,
                        isWarning = true
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                }
            }

            Text("✅ Health Connect Connected", color = MaterialTheme.colorScheme.primary)
            Spacer(modifier = Modifier.height(16.dp))

            if (walkData != null) {
                Card(
                    elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("Detailed Activity Report", style = MaterialTheme.typography.titleLarge)
                        Divider(modifier = Modifier.padding(vertical = 8.dp))
                        
                        InfoRow("Steps (24h)", "${walkData!!.totalSteps}")
                        
                        InfoRow("Distance", "${String.format("%.2f", walkData!!.totalDistanceMeters / 1609.34)} miles")
                        Text("Source: ${walkData!!.distanceSource}", 
                             style = MaterialTheme.typography.labelSmall,
                             color = if (walkData!!.distanceSource.startsWith("Health Connect")) 
                                 MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.secondary)
                        
                        Spacer(modifier = Modifier.height(8.dp))
                        InfoRow("Walking Sessions", "${walkData!!.walkingSessionsCount}")
                        InfoRow("GPS Route Found", if(walkData!!.hasExerciseRoutes) "YES 📍 (${walkData!!.routePointCount} pts)" else "NO")
                        
                        Divider(modifier = Modifier.padding(vertical = 8.dp))
                        
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("Walk Inferred: ", style = MaterialTheme.typography.titleMedium)
                            Text(
                                if(walkData!!.isWalkInferred) "YES 🐕" else "NO",
                                style = MaterialTheme.typography.titleLarge,
                                color = if(walkData!!.isWalkInferred) MaterialTheme.colorScheme.primary 
                                        else MaterialTheme.colorScheme.error
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(32.dp))

            Button(
                onClick = { onLogWalk(1.0) },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.secondary)
            ) {
                Text("Log Walk to Beeminder (Direct)")
            }
            
            TextButton(onClick = { 
                scope.launch { 
                    walkData = healthManager.fetchRecentWalkData() 
                }
            }) {
                Text("Refresh Data")
            }
        }
    }
}

@Composable
fun PermissionCard(
    title: String,
    description: String,
    buttonText: String,
    onGrant: () -> Unit,
    onOpenSettings: (() -> Unit)? = null,
    isWarning: Boolean = false
) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = if (isWarning) MaterialTheme.colorScheme.tertiaryContainer 
                             else MaterialTheme.colorScheme.errorContainer
        ),
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(description, style = MaterialTheme.typography.bodyMedium)
            Spacer(modifier = Modifier.height(16.dp))
            Row(modifier = Modifier.align(Alignment.End)) {
                if (onOpenSettings != null) {
                    TextButton(onClick = onOpenSettings) {
                        Text("Open Settings")
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                }
                Button(onClick = onGrant) {
                    Text(buttonText)
                }
            }
        }
    }
}

@Composable
fun InfoRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(label, style = MaterialTheme.typography.bodyMedium)
        Text(value, style = MaterialTheme.typography.bodyLarge)
    }
}
