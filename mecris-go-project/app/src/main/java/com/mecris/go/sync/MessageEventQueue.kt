package com.mecris.go.sync

import android.content.Context
import com.google.gson.Gson
import com.google.gson.JsonParseException
import java.io.IOException

/**
 * Durable local queue of phone nag events (#363 phase 1). Receivers and
 * MainActivity enqueue; MessageEventUploadWorker drains it to
 * POST /internal/log-message-event. Capped at [cap] (oldest dropped first) so a
 * long offline stretch can't grow it without bound. Holds no message text.
 */
class MessageEventQueue(private val store: Store, private val cap: Int = DEFAULT_CAP) {

    interface Store {
        fun read(): String?
        fun write(json: String)
    }

    enum class Outcome { DROP, RETRY }

    fun enqueue(event: MessageEventRequestDto) = synchronized(LOCK) {
        save((load() + event).takeLast(cap))
    }

    fun pending(): List<MessageEventRequestDto> = synchronized(LOCK) { load() }

    /**
     * Sends a snapshot of the queue in order. [send] returns the HTTP code or throws
     * IOException. Stops at the first retryable failure (the server or network is
     * likely down). Returns true when something is left that is worth retrying.
     * Events enqueued while sending are kept.
     */
    suspend fun drain(send: suspend (MessageEventRequestDto) -> Int): Boolean {
        val snapshot = pending()
        val done = mutableListOf<MessageEventRequestDto>()
        var retry = false
        for (event in snapshot) {
            val outcome = try {
                outcomeFor(send(event))
            } catch (e: IOException) {
                Outcome.RETRY
            }
            if (outcome == Outcome.RETRY) {
                retry = true
                break
            }
            done.add(event)
        }
        if (done.isNotEmpty()) synchronized(LOCK) {
            val remaining = load().toMutableList()
            done.forEach { remaining.remove(it) }
            save(remaining)
        }
        return retry
    }

    private fun load(): List<MessageEventRequestDto> {
        val json = store.read() ?: return emptyList()
        return try {
            gson.fromJson(json, Array<MessageEventRequestDto>::class.java)?.toList() ?: emptyList()
        } catch (e: JsonParseException) {
            emptyList()
        }
    }

    private fun save(events: List<MessageEventRequestDto>) = store.write(gson.toJson(events))

    companion object {
        const val DEFAULT_CAP = 200

        private val LOCK = Any()
        private val gson = Gson()

        private const val PREFS = "mecris_message_events"
        private const val KEY = "queue"

        /**
         * 2xx (201 inserted, 200 already recorded) and 404 (unknown nag) are final.
         * 400 is a bad body: resending the same bytes can't help either.
         * Everything else (401 expired token, 429, 5xx) is worth another try.
         */
        fun outcomeFor(code: Int): Outcome = when {
            code in 200..299 -> Outcome.DROP
            code == 404 || code == 400 -> Outcome.DROP
            else -> Outcome.RETRY
        }

        /** The app's queue, kept in SharedPreferences and written with commit(). */
        fun forContext(context: Context): MessageEventQueue {
            val prefs = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            return MessageEventQueue(object : Store {
                override fun read(): String? = prefs.getString(KEY, null)
                override fun write(json: String) {
                    prefs.edit().putString(KEY, json).commit()
                }
            })
        }
    }
}
