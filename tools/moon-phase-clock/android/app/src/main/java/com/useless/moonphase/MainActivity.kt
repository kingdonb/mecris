package com.useless.moonphase

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        val wasmEngine = try {
            WasmEngine(assets.open("moon-phase.wasm"))
        } catch (e: Exception) {
            null
        }
        
        setContent {
            MaterialTheme(colorScheme = darkColorScheme()) {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = Color(0xFF0D0D0D)
                ) {
                    MoonPhaseScreen(wasmEngine)
                }
            }
        }
    }
}

@Composable
fun MoonPhaseScreen(engine: WasmEngine?) {
    var moonData by remember { mutableStateOf<JSONObject?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        if (engine == null) {
            error = "WASM Brain not found in assets!"
            return@LaunchedEffect
        }
        try {
            val now = System.currentTimeMillis() / 1000.0
            val result = engine.calculatePhase(now)
            moonData = JSONObject(result)
        } catch (e: Exception) {
            error = e.message
        }
    }

    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            text = "THE ORACLE",
            style = MaterialTheme.typography.labelLarge,
            color = Color.Gray,
            letterSpacing = 4.sp
        )
        
        Spacer(modifier = Modifier.height(32.dp))

        if (error != null) {
            android.util.Log.e("MoonPhase", "WASM Error: $error")
            Text(text = error!!, color = Color.Red)
        } else if (moonData == null) {
            CircularProgressIndicator(color = Color.White)
        } else {
            val phase = moonData!!.getString("phase_name")
            val illum = (moonData!!.getDouble("illumination") * 100).toInt()
            val multiplier = moonData!!.getDouble("torment_multiplier")
            
            android.util.Log.d("MoonPhase", "WASM Execution Success: $phase ($illum%) Multiplier: $multiplier")

            Text(
                text = phase.uppercase(),
                style = MaterialTheme.typography.headlineLarge,
                color = Color.White,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center
            )
            
            Text(
                text = "$illum% ILLUMINATED",
                style = MaterialTheme.typography.bodyLarge,
                color = Color.LightGray
            )

            Spacer(modifier = Modifier.height(48.dp))
            
            // Torment Gauge
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(80.dp)
                    .background(Color.White.copy(alpha = 0.05f), RoundedCornerShape(8.dp))
                    .padding(16.dp),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(
                        text = "TORMENT MULTIPLIER",
                        style = MaterialTheme.typography.labelSmall,
                        color = if (multiplier >= 3.0) Color.Red else Color.Gray
                    )
                    Text(
                        text = "${multiplier}x",
                        style = MaterialTheme.typography.displaySmall,
                        color = if (multiplier >= 3.0) Color.Red else Color.White,
                        fontWeight = FontWeight.Black
                    )
                }
            }
            
            if (multiplier >= 3.0) {
                Spacer(modifier = Modifier.height(16.dp))
                Text(
                    text = "THE BOAR GOD CHARGES",
                    style = MaterialTheme.typography.labelMedium,
                    color = Color.Red,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}
