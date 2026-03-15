package com.mecris.go.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

import com.mecris.go.health.HealthConnectManager
import com.mecris.go.health.WalkDataSummary

class IntegrationsActivity : ComponentActivity() {
    private lateinit var healthConnectManager: HealthConnectManager

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        healthConnectManager = HealthConnectManager(this)
        
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
                        onBack = { finish() }
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun IntegrationsScreen(healthManager: HealthConnectManager, onBack: () -> Unit) {
    var walkData by remember { mutableStateOf<WalkDataSummary?>(null) }
    
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
                val momentumValue = if (walkData?.isWalkInferred == true) 0.9f else 0.3f
                MomentumVisualizer(momentum = momentumValue)
            }
            
            Spacer(modifier = Modifier.height(16.dp))
            
            OdometerView(
                value = 21.00,
                label = "VIRTUAL BUDGET"
            )

            Spacer(modifier = Modifier.height(8.dp))

            val miles = (walkData?.totalDistanceMeters ?: 0.0) / 1609.34
            OdometerView(
                value = miles,
                label = "TODAY'S DISTANCE",
                symbol = "MI",
                symbolColor = Color(0xFF00E5FF),
                digits = 4,
                decimalPlaces = 2
            )
            
            Spacer(modifier = Modifier.height(24.dp))
            
            IntegrationCard(
                name = "BEEMINDER",
                status = "CONNECTED",
                description = "Emergency monitoring for reviewstack, ellinika, and bike.",
                color = Color(0xFFFFD600)
            )
            
            Spacer(modifier = Modifier.height(16.dp))
            
            IntegrationCard(
                name = "NEON CLOUD",
                status = "SYNC ACTIVE",
                description = "Spin-sync backend for distributed walk tracking.",
                color = Color(0xFF00E5FF)
            )
            
            Spacer(modifier = Modifier.height(16.dp))
            
            IntegrationCard(
                name = "POCKET ID",
                status = "AUTHENTICATED",
                description = "Biometric decentralized identity provider.",
                color = Color(0xFFAA00FF)
            )
        }
    }
}

@Composable
fun IntegrationCard(name: String, status: String, description: String, color: Color) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF1E1E1E))
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = name,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = color
                )
                Text(
                    text = status,
                    style = MaterialTheme.typography.labelSmall,
                    color = Color.Gray
                )
            }
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = description,
                style = MaterialTheme.typography.bodySmall,
                color = Color.LightGray
            )
        }
    }
}
