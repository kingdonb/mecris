package com.mecris.go.sync

import java.util.UUID

/**
 * Phase 1 of docs/WALK_REMINDERS.md (#363): the phone's side of "see what happens".
 * Every shown nag carries a client_ref, and taps, dismissals and action buttons are
 * recorded against it (contracts/message_events.json).
 */
object NagEvents {
    const val TAPPED = "tapped"
    const val DISMISSED = "dismissed"
    const val ACTION_LATER = "action_later"
    const val ACTION_START = "action_start"

    /** contracts/message_events.json event_vocabulary.phone. */
    val PHONE_EVENTS: Set<String> = setOf(TAPPED, DISMISSED, ACTION_LATER, ACTION_START)

    const val EXTRA_CLIENT_REF = "com.mecris.go.extra.NAG_CLIENT_REF"
    const val EXTRA_EVENT = "com.mecris.go.extra.NAG_EVENT"

    /** client_ref_rule: 1-64 characters from [A-Za-z0-9-]. */
    private val CLIENT_REF_RULE = Regex("[A-Za-z0-9-]{1,64}")

    fun newClientRef(): String = UUID.randomUUID().toString()

    fun isValidClientRef(ref: String?): Boolean = ref != null && CLIENT_REF_RULE.matches(ref)
}
