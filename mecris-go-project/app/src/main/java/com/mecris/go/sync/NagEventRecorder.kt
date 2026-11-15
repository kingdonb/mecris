package com.mecris.go.sync

import android.content.Context
import android.content.Intent
import android.util.Log
import androidx.core.app.NotificationManagerCompat
import com.mecris.go.health.WalkSuppression
import java.time.Instant

/**
 * Records what happened to a shown nag (#363 phase 1): queue the event durably,
 * schedule the upload, and apply any local walk suppression. Logs only the event
 * name, never message text or the token.
 */
object NagEventRecorder {
    private const val TAG = "NagEventRecorder"
    private const val WORKER_PREFS = "mecris_worker_state"

    fun record(context: Context, clientRef: String?, event: String, at: Instant = Instant.now()) {
        if (event !in NagEvents.PHONE_EVENTS || !NagEvents.isValidClientRef(clientRef)) {
            Log.w(TAG, "Ignoring nag event without a valid ref or name: $event")
            return
        }
        MessageEventQueue.forContext(context).enqueue(MessageEventRequestDto.of(clientRef!!, event, at))
        MessageEventUploadWorker.schedule(context)
        Log.i(TAG, "Nag event queued: $event")
    }

    /**
     * Queue a nag's shown row (POST /internal/log-message) so the uploader sends it
     * before any of that nag's events. The only path that logs a shown nag.
     */
    fun recordShown(context: Context, shown: LogMessageRequestDto) {
        MessageEventQueue.forContext(context).enqueueShown(shown)
        MessageEventUploadWorker.schedule(context)
        Log.i(TAG, "Nag shown row queued: ${shown.type}")
    }

    /** Suppress walk nags until [untilMs], never shortening an existing suppression. */
    fun suppressWalkUntil(context: Context, untilMs: Long) {
        val prefs = context.applicationContext.getSharedPreferences(WORKER_PREFS, Context.MODE_PRIVATE)
        val merged = WalkSuppression.merge(prefs.getLong(WalkSuppression.PREF_KEY, 0L), untilMs)
        prefs.edit().putLong(WalkSuppression.PREF_KEY, merged).commit()
    }

    fun cancelNag(context: Context) {
        NotificationManagerCompat.from(context).cancel(NagNotificationManager.NOTIFICATION_ID)
    }

    /**
     * MainActivity's side: a tap or START arrives as activity extras (no trampoline).
     * Returns true when the intent carried a nag event. Strips the extras so a
     * configuration change or relaunch doesn't record it twice.
     */
    fun handleActivityIntent(context: Context, intent: Intent?): Boolean {
        if (intent == null) return false
        if (intent.flags and Intent.FLAG_ACTIVITY_LAUNCHED_FROM_HISTORY != 0) return false
        val event = intent.getStringExtra(NagEvents.EXTRA_EVENT) ?: return false
        val ref = intent.getStringExtra(NagEvents.EXTRA_CLIENT_REF)
        intent.removeExtra(NagEvents.EXTRA_EVENT)
        intent.removeExtra(NagEvents.EXTRA_CLIENT_REF)

        when (event) {
            NagEvents.TAPPED -> record(context, ref, NagEvents.TAPPED)
            NagEvents.ACTION_START -> {
                record(context, ref, NagEvents.ACTION_START)
                val now = Instant.now()
                suppressWalkUntil(context, WalkSuppression.endOfNewYorkDay(now).toEpochMilli())
            }
            else -> return false
        }
        // Action buttons don't auto-cancel; the content tap already did.
        cancelNag(context)
        return true
    }
}
