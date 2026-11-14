package com.mecris.go.health

import com.mecris.go.sync.PaceDto

/** Nag wording helpers (#349). */
object NagCopy {
    /** The pace line for an Arabic or Greek nag, or null when there is nothing to add. */
    fun paceLine(goal: String, pace: List<PaceDto>?): String? = TODO("#349")

    /** [message] with the pace line appended on its own line, or unchanged. */
    fun withPace(message: String, goal: String, pace: List<PaceDto>?): String = TODO("#349")
}
