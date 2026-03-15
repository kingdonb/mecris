package com.mecris.go.ui

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import kotlin.math.sin

@Composable
fun MomentumVisualizer(momentum: Float) {
    val infiniteTransition = rememberInfiniteTransition(label = "momentum")
    
    // Scale pulse based on momentum
    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 0.8f,
        targetValue = 1.2f,
        animationSpec = infiniteRepeatable(
            animation = tween(2000, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulse"
    )

    // Rotation for the "living" feel
    val rotation by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(10000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "rotation"
    )

    // Colors shift from blue/green (safe) to red/yellow (emergency)
    val color1 = remember(momentum) {
        if (momentum > 0.5f) Color(0xFF00C853) else Color(0xFFFF1744)
    }
    val color2 = remember(momentum) {
        if (momentum > 0.5f) Color(0xFF2979FF) else Color(0xFFFFEA00)
    }

    Canvas(modifier = Modifier
        .fillMaxSize()
        .graphicsLayer(
            scaleX = pulseScale * (0.8f + momentum * 0.4f),
            scaleY = pulseScale * (0.8f + momentum * 0.4f),
            rotationZ = rotation
        )
    ) {
        val canvasWidth = size.width
        val canvasHeight = size.height
        
        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(color1.copy(alpha = 0.8f), color2.copy(alpha = 0.2f), Color.Transparent),
                center = Offset(canvasWidth / 2, canvasHeight / 2),
                radius = canvasWidth / 2
            ),
            radius = canvasWidth / 2,
            center = Offset(canvasWidth / 2, canvasHeight / 2)
        )
        
        // Add some "floaties" or particles
        for (i in 0..5) {
            val angle = (rotation + i * 60) * (Math.PI / 180).toFloat()
            val x = canvasWidth / 2 + (canvasWidth / 3) * kotlin.math.cos(angle)
            val y = canvasHeight / 2 + (canvasWidth / 3) * sin(angle)
            drawCircle(
                color = color1.copy(alpha = 0.4f),
                radius = 20f,
                center = Offset(x, y)
            )
        }
    }
}
