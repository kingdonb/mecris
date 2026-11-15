package com.mecris.go.sync

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.mecris.go.MainActivity

/**
 * Shows local nags. It does not log them: DelayedNagWorker awaits the #213 audit
 * call itself, with the bearer, after the cooldown write, using the client_ref
 * that [showNag] returns.
 */
class NagNotificationManager(
    private val context: Context
) {

    companion object {
        const val CHANNEL_ID = "mecris_nag_channel"
        private const val CHANNEL_NAME = "Mecris Accountability Nag"
        const val NOTIFICATION_ID = 1001

        private const val WALK_TYPE = "walk_reminder"

        // Distinct request codes: PendingIntent identity ignores extras.
        private const val REQ_TAP = 0
        private const val REQ_LAUNCH = 1
        private const val REQ_DISMISS = 2
        private const val REQ_LATER = 3
        private const val REQ_START = 4

        /** #363 heartbeat: app notifications on AND the nag channel not silenced. */
        fun notificationsEnabled(appEnabled: Boolean, channelImportance: Int?): Boolean =
            appEnabled && channelImportance != NotificationManager.IMPORTANCE_NONE

        /**
         * The heartbeat's notifications_enabled for this device right now; null (so
         * the field is omitted) if the system can't be asked.
         */
        fun notificationsEnabled(context: Context): Boolean? = try {
            val compat = NotificationManagerCompat.from(context)
            notificationsEnabled(
                compat.areNotificationsEnabled(),
                compat.getNotificationChannel(CHANNEL_ID)?.importance
            )
        } catch (e: RuntimeException) {
            null
        }
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

    /**
     * Shows a nag and returns its new client_ref (#363 phase 1). [type] is the
     * message_log type the caller logs this nag under, with the same client_ref.
     *
     * Tap and START are activity PendingIntents straight to MainActivity (Android 12+
     * forbids notification trampolines); dismiss and LATER go to the non-exported
     * NagActionReceiver. Walk nags carry LATER and START, the same words WhatsApp
     * replies will use; language nags keep DO CARDS and DASHBOARD.
     */
    fun showNag(title: String, message: String, packageToLaunch: String? = null, type: String = "unknown"): String {
        val clientRef = NagEvents.newClientRef()

        val dashboardPendingIntent = activityIntent(REQ_TAP, clientRef, NagEvents.TAPPED)
        val deletePendingIntent = receiverIntent(REQ_DISMISS, clientRef, NagActionReceiver.ACTION_DISMISSED)

        val builder = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle(title)
            .setContentText(message)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setAutoCancel(true)
            .setContentIntent(dashboardPendingIntent)
            .setDeleteIntent(deletePendingIntent)
            .setStyle(NotificationCompat.BigTextStyle().bigText(message))

        if (type == WALK_TYPE) {
            builder.addAction(0, "LATER", receiverIntent(REQ_LATER, clientRef, NagActionReceiver.ACTION_LATER))
            builder.addAction(0, "START", activityIntent(REQ_START, clientRef, NagEvents.ACTION_START))
        } else if (packageToLaunch != null) {
            // Language nags: quick action for the work itself, plus the dashboard.
            val launchIntent = context.packageManager.getLaunchIntentForPackage(packageToLaunch)
            if (launchIntent != null) {
                val launchPendingIntent = PendingIntent.getActivity(
                    context, REQ_LAUNCH, launchIntent,
                    PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
                )
                val actionTitle = if (packageToLaunch.contains("clozemaster")) "DO CARDS" else "GO WALK"
                builder.addAction(0, actionTitle, launchPendingIntent)
                builder.addAction(0, "DASHBOARD", dashboardPendingIntent)
            }
        }

        val notificationManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        notificationManager.notify(NOTIFICATION_ID, builder.build())
        Log.d("NagNotificationManager", "Nag shown: $type")
        return clientRef
    }

    private fun activityIntent(requestCode: Int, clientRef: String, event: String): PendingIntent {
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
            putExtra(NagEvents.EXTRA_CLIENT_REF, clientRef)
            putExtra(NagEvents.EXTRA_EVENT, event)
        }
        return PendingIntent.getActivity(
            context, requestCode, intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
    }

    private fun receiverIntent(requestCode: Int, clientRef: String, action: String): PendingIntent {
        val intent = Intent(context, NagActionReceiver::class.java).apply {
            this.action = action
            putExtra(NagEvents.EXTRA_CLIENT_REF, clientRef)
        }
        return PendingIntent.getBroadcast(
            context, requestCode, intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
    }
}
