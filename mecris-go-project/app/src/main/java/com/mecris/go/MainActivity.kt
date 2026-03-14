package com.mecris.go

import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
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
        val requestPermissions = registerForActivityResult(requestPermissionActivityContract) { granted ->
            if (granted.containsAll(healthConnectManager.permissions)) {
                Toast.makeText(this, "Health Connect permissions granted", Toast.LENGTH_SHORT).show()
                recreate()
            } else {
                Toast.makeText(this, "Some permissions were denied", Toast.LENGTH_LONG).show()
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
                        onRequestPermissions = {
                            requestPermissions.launch(healthConnectManager.permissions)
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
    onRequestPermissions: () -> Unit,
    onLogWalk: (Double) -> Unit
) {
    val scope = rememberCoroutineScope()
    var walkData by remember { mutableStateOf<WalkDataSummary?>(null) }
    var hasPermissions by remember { mutableStateOf(false) }
    var isLoading by remember { mutableStateOf(true) }

    // Check permissions and fetch data on load
    LaunchedEffect(Unit) {
        isLoading = true
        hasPermissions = healthManager.hasAllPermissions()
        if (hasPermissions) {
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
        } else if (!hasPermissions) {
            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
                modifier = Modifier.fillMaxWidth().padding(16.dp)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Permissions Missing", style = MaterialTheme.typography.titleMedium)
                    Text("Mecris-Go needs access to your steps and distance to track your dog walks.",
                         style = MaterialTheme.typography.bodyMedium)
                    Spacer(modifier = Modifier.height(16.dp))
                    Button(
                        onClick = onRequestPermissions,
                        modifier = Modifier.align(Alignment.End)
                    ) {
                        Text("Grant Permissions")
                    }
                }
            }
        } else {
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
                        
                        InfoRow("Steps (23h)", "${walkData!!.totalSteps}")
                        
                        InfoRow("Distance", "${String.format("%.2f", walkData!!.totalDistanceMeters / 1609.34)} miles")
                        Text("Source: ${walkData!!.distanceSource}", 
                             style = MaterialTheme.typography.labelSmall,
                             color = if (walkData!!.distanceSource == "Health Connect") 
                                 MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.secondary)
                        
                        Spacer(modifier = Modifier.height(8.dp))
                        InfoRow("Walking Sessions", "${walkData!!.walkingSessionsCount}")
                        InfoRow("GPS Route Found", if(walkData!!.hasExerciseRoutes) "YES 📍" else "NO")
                        
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
fun InfoRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(label, style = MaterialTheme.typography.bodyMedium)
        Text(value, style = MaterialTheme.typography.bodyLarge)
    }
}
