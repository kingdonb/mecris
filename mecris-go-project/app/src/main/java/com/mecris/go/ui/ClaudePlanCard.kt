package com.mecris.go.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.mecris.go.model.ClaudePlanState
import com.mecris.go.model.ClaudePlanView
import com.mecris.go.model.formatAge

private val CardBackground = Color(0xFF1E1E1E)

private fun stateColor(state: String): Color = when (state) {
    ClaudePlanState.AVAILABLE -> Color(0xFF00C853)
    ClaudePlanState.CONSTRAINED -> Color(0xFFFFD600)
    ClaudePlanState.EXHAUSTED -> Color(0xFFFF1744)
    else -> Color.Gray
}

/**
 * Claude plan card (#344): replaces the API-era VIRTUAL BUDGET odometer. Stateless;
 * the caller derives [view] with ClaudePlanState.derive(claude_plan, now), so cached
 * data turns 'unknown' once it is over 24 h old or the weekly window has reset.
 */
@Composable
fun ClaudePlanCard(view: ClaudePlanView, modifier: Modifier = Modifier) {
    val color = stateColor(view.state)
    Surface(
        modifier = modifier.fillMaxWidth().padding(vertical = 4.dp),
        color = CardBackground,
        shape = RoundedCornerShape(8.dp)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "CLAUDE PLAN" + (view.plan?.let { " · ${it.uppercase()}" } ?: ""),
                    style = MaterialTheme.typography.labelSmall,
                    color = Color.Gray,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.sp
                )
                Text(
                    text = if (view.hasReading) view.state.uppercase() else "NO READING",
                    modifier = Modifier
                        .background(color.copy(alpha = 0.2f), RoundedCornerShape(4.dp))
                        .padding(horizontal = 6.dp, vertical = 2.dp),
                    style = MaterialTheme.typography.labelSmall,
                    color = color,
                    fontWeight = FontWeight.ExtraBold
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            val pct = view.weeklyPct
            if (pct != null) {
                Text(
                    text = "${String.format(java.util.Locale.US, "%.0f", pct)}% of weekly limit used",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color.White,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(4.dp))
                LinearProgressIndicator(
                    progress = { (pct / 100.0).toFloat().coerceIn(0f, 1f) },
                    modifier = Modifier.fillMaxWidth().height(6.dp),
                    color = color,
                    trackColor = Color(0xFF333333)
                )
                view.weeklyResetsLabel?.let {
                    Spacer(modifier = Modifier.height(4.dp))
                    Text("Resets $it (New York)", style = MaterialTheme.typography.bodySmall, color = Color.LightGray)
                }
            } else {
                Text(
                    text = if (view.hasReading) view.reason.replaceFirstChar { it.uppercase() } else "No reading recorded yet",
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.LightGray
                )
            }

            if (view.hasReading) {
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "Reading ${formatAge(view.ageMinutes)}" +
                        if (view.state != ClaudePlanState.UNKNOWN && view.reason.isNotEmpty()) " · binding: ${view.reason}" else "",
                    style = MaterialTheme.typography.labelSmall,
                    color = Color.Gray
                )
            }
        }
    }
}
