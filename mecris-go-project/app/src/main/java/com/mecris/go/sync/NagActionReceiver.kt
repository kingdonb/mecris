package com.mecris.go.sync

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.mecris.go.health.WalkSuppression
import java.time.Instant

/**
 * Not exported. Receives a nag's delete intent (swiped away) and the walk nag's
 * LATER button (#363 phase 1). Starts no activity: Android 12+ forbids
 * notification trampolines, so taps and START go straight to MainActivity.
 */
class NagActionReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        val ref = intent.getStringExtra(NagEvents.EXTRA_CLIENT_REF)
        when (intent.action) {
            ACTION_DISMISSED -> NagEventRecorder.record(context, ref, NagEvents.DISMISSED)
            ACTION_LATER -> {
                NagEventRecorder.record(context, ref, NagEvents.ACTION_LATER)
                // Phase 1 keeps the snooze local and fixed at 90 minutes. Phase 2
                // moves the decision to the cloud decider (docs/WALK_REMINDERS.md),
                // which picks a time that still has daylight.
                NagEventRecorder.suppressWalkUntil(
                    context,
                    WalkSuppression.laterUntil(Instant.now()).toEpochMilli()
                )
                NagEventRecorder.cancelNag(context)
            }
        }
    }

    companion object {
        const val ACTION_DISMISSED = "com.mecris.go.action.NAG_DISMISSED"
        const val ACTION_LATER = "com.mecris.go.action.NAG_LATER"
    }
}
