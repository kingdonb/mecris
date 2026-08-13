package com.mecris.go.auth

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import androidx.annotation.RequiresApi
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext
import com.mecris.go.MainActivity
import kotlinx.datetime.Instant
import kotlinx.serialization.json.Json

/**
 * Handles user-facing error reporting for authentication failures.
 * Contract: non-modal snackbar + persistent notification with deep-link to auth screen.
 */
class AuthErrorReporter(
    private val context: Context,
    private val notificationManager: NotificationManagerCompat = NotificationManagerCompat.from(context)
) {

    companion object {
        private const val CHANNEL_ID = "mecris_auth_errors"
        private const val NOTIFICATION_ID = 41001
    }

    init {
        createNotificationChannel()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Mecris Authentication",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Critical authentication errors requiring user action"
                enableVibration(true)
                setShowBadge(true)
            }
            val manager = context.getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    /**
     * Reports an auth error via snackbar (if UI is visible) and persistent notification.
     * @param error The classified auth error
     * @param lastKnownEmail Optional email to pre-fill on auth screen deep-link
     * @param lifecycleOwner Optional lifecycle owner to show snackbar (null = skip snackbar)
     * @param snackbarAnchorView Optional anchor view for snackbar
     */
    fun report(
        error: AuthError,
        lastKnownEmail: String? = null
    ) {
        // 1. Persistent notification (always shown)
        showNotification(error, lastKnownEmail)
    }

    private fun showNotification(error: AuthError, lastKnownEmail: String? = null) {
        val intent = Intent(context, MainActivity::class.java).apply {
            action = Intent.ACTION_MAIN
            addCategory(Intent.CATEGORY_LAUNCHER)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            putExtra("trigger_auth", true)
            lastKnownEmail?.let { putExtra("prefill_email", it) }
        }
        val pendingIntent = PendingIntent.getActivity(
            context,
            0,
            intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        val detailText = error.detail?.let { "\nDetail: $it" } ?: ""
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle("Mecris needs your attention")
            .setContentText("${error.errorCode}: ${error.message}")
            .setStyle(
                NotificationCompat.BigTextStyle()
                    .bigText("${error.errorCode}\n${error.message}$detailText")
            )
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_ERROR)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .setOngoing(error.isPermanent) // Permanent errors stay until dismissed
            .build()

        notificationManager.notify(NOTIFICATION_ID, notification)
    }



    /** Clears the persistent auth notification (e.g., after successful re-auth). */
    fun clearNotification() {
        notificationManager.cancel(NOTIFICATION_ID)
    }
}


/**
 * Composable helper to get AuthErrorReporter instance.
 */
@Composable
fun rememberAuthErrorReporter(): AuthErrorReporter {
    val ctx = LocalContext.current
    return remember(ctx) { AuthErrorReporter(ctx) }
}
