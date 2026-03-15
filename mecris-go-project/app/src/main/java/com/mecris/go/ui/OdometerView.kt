package com.mecris.go.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun OdometerView(
    value: Double, 
    label: String = "BUDGET REMAINING", 
    symbol: String = "$",
    symbolColor: Color = Color.White,
    digitColor: Color = Color(0xFFFFD600), // Default yellow
    digits: Int = 7,
    decimalPlaces: Int = 2
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(8.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = Color.Gray
        )
        
        Spacer(modifier = Modifier.height(4.dp))
        
        Row(
            modifier = Modifier
                .background(Color.Black, RoundedCornerShape(4.dp))
                .padding(horizontal = 8.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (symbol.isNotEmpty()) {
                Text(
                    text = symbol,
                    color = symbolColor,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.width(4.dp))
            }
            
            val formatStr = "%0${digits + (if (decimalPlaces > 0) 1 else 0)}.${decimalPlaces}f"
            val formattedValue = String.format(formatStr, value)
            formattedValue.forEach { char ->
                Box(
                    modifier = Modifier
                        .padding(horizontal = 1.dp)
                        .background(
                            if (char == '.') Color.Transparent else Color(0xFF212121),
                            RoundedCornerShape(2.dp)
                        )
                        .padding(horizontal = 3.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = char.toString(),
                        color = if (char == '.') Color.White else digitColor,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 24.sp,
                        fontWeight = FontWeight.ExtraBold
                    )
                }
            }
        }
    }
}
