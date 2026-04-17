package com.mecris.go.sync

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import com.mecris.go.MainActivity
import com.mecris.go.R

class NagNotificationManager(private val context: Context) {

    companion object {
        private const val CHANNEL_ID = "mecris_nag_channel"
        private const val CHANNEL_NAME = "Mecris Accountability Nag"
        private const val NOTIFICATION_ID = 1001
    }

    init {
        createNotificationChannel()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val importance = NotificationManager.IMPORTANCE_HIGH
            val channel = NotificationChannel(CHANNEL_ID, CHANNEL_NAME, importance).apply {
                description = "Urgent reminders for language reviews and physical activity"
                enableLights(true)
                enableVibration(true)
            }
            val notificationManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            notificationManager.createNotificationChannel(channel)
        }
    }

    fun showNag(title: String, message: String, packageToLaunch: String? = null) {
        val dashboardIntent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        }
        val dashboardPendingIntent = PendingIntent.getActivity(
            context, 0, dashboardIntent, 
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        val builder = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle(title)
            .setContentText(message)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setAutoCancel(true)
            .setContentIntent(dashboardPendingIntent)
            .setStyle(NotificationCompat.BigTextStyle().bigText(message))

        // Add Quick Action for the work itself
        if (packageToLaunch != null) {
            val launchIntent = context.packageManager.getLaunchIntentForPackage(packageToLaunch)
            if (launchIntent != null) {
                val launchPendingIntent = PendingIntent.getActivity(
                    context, 1, launchIntent,
                    PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
                )
                val actionTitle = if (packageToLaunch.contains("clozemaster")) "DO CARDS" else "GO WALK"
                builder.addAction(0, actionTitle, launchPendingIntent)
                builder.addAction(0, "DASHBOARD", dashboardPendingIntent)
            }
        }

        val notificationManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        notificationManager.notify(NOTIFICATION_ID, builder.build())
    }
}
