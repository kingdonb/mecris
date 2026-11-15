package com.mecris.go.sync

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
    val PHONE_EVENTS: Set<String> = emptySet()

    const val EXTRA_CLIENT_REF = "com.mecris.go.extra.NAG_CLIENT_REF"
    const val EXTRA_EVENT = "com.mecris.go.extra.NAG_EVENT"

    fun newClientRef(): String = ""

    fun isValidClientRef(ref: String?): Boolean = false
}
