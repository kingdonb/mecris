package com.mecris.go.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.mecris.go.model.PulseRow

private fun pulseColor(status: String): Color = when (status.lowercase()) {
    "healthy" -> Color(0xFF00C853)
    "degraded" -> Color(0xFFFFD600)
    "offline" -> Color(0xFFFF1744)
    "paused" -> Color(0xFF90A4AE)
    else -> Color.Gray
}

/**
 * Compact system pulse (#346, #245): each modality's status and age, plus the cloud
 * cron's latest outcome line, so the phone shows what the cron last decided.
 * Renders nothing until a full aggregate-status has been fetched.
 */
@Composable
fun SystemPulseCard(rows: List<PulseRow>, modifier: Modifier = Modifier) {
    if (rows.isEmpty()) return
    Surface(
        modifier = modifier.fillMaxWidth().padding(vertical = 4.dp),
        color = Color(0xFF1E1E1E),
        shape = RoundedCornerShape(8.dp)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(
                "SYSTEM PULSE",
                style = MaterialTheme.typography.labelSmall,
                color = Color.Gray,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp
            )
            Spacer(modifier = Modifier.height(6.dp))
            rows.forEach { row ->
                val color = pulseColor(row.status)
                Row(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(modifier = Modifier.size(8.dp).background(color, CircleShape))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        row.role,
                        modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.labelSmall,
                        color = Color.White,
                        fontWeight = FontWeight.Bold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Text(
                        "${row.status.uppercase()} · ${row.age}",
                        style = MaterialTheme.typography.labelSmall,
                        color = color
                    )
                }
                row.lastStatus?.let {
                    Text(
                        it,
                        modifier = Modifier.padding(start = 16.dp, bottom = 2.dp),
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.LightGray,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
        }
    }
}
