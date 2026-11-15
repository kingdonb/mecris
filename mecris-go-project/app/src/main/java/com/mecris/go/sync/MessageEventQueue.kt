package com.mecris.go.sync

import android.content.Context
import com.google.gson.Gson
import com.google.gson.JsonParseException
import java.io.IOException

/**
 * Durable local queue of what happened to each nag (#363 phase 1). It holds two
 * kinds of item, keyed by client_ref:
 *  - the nag's shown row, for POST /internal/log-message (queued by DelayedNagWorker);
 *  - its events, for POST /internal/log-message-event (receivers and MainActivity).
 *
 * Spin answers 404 to an event whose nag it hasn't logged, so a nag's shown row is
 * always sent first and its events wait behind it. MessageEventUploadWorker drains
 * it. Capped at [cap] items; the oldest whole nag is evicted, never just its shown
 * row. Holds no message text.
 */
class MessageEventQueue(private val store: Store, private val cap: Int = DEFAULT_CAP) {

    interface Store {
        fun read(): String?
        fun write(json: String)
    }

    /** DONE: landed. DROP: retrying can't help. RETRY: keep it and try later. */
    enum class Outcome { DONE, DROP, RETRY }

    /** One stored item; Gson-friendly, so every field but [kind] is nullable. */
    data class Item(
        val kind: String,
        val client_ref: String? = null,
        val type: String? = null,
        val sent_at: String? = null,
        val event: String? = null,
        val at: String? = null
    ) {
        val isShown: Boolean get() = kind == KIND_SHOWN

        fun toShown() = LogMessageRequestDto(
            type = type ?: "",
            channel = LogMessageRequestDto.CHANNEL_ANDROID_NATIVE,
            sent_at = sent_at,
            client_ref = client_ref
        )

        fun toEvent() = MessageEventRequestDto(client_ref = client_ref ?: "", event = event ?: "", at = at ?: "")

        companion object {
            fun of(shown: LogMessageRequestDto) =
                Item(KIND_SHOWN, client_ref = shown.client_ref, type = shown.type, sent_at = shown.sent_at)

            fun of(event: MessageEventRequestDto) =
                Item(KIND_EVENT, client_ref = event.client_ref, event = event.event, at = event.at)
        }
    }

    fun enqueueShown(shown: LogMessageRequestDto) = add(Item.of(shown))

    fun enqueue(event: MessageEventRequestDto) = add(Item.of(event))

    fun pending(): List<Item> = synchronized(LOCK) { load() }

    fun pendingShown(): List<LogMessageRequestDto> = pending().filter { it.isShown }.map { it.toShown() }

    fun pendingEvents(): List<MessageEventRequestDto> = pending().filter { !it.isShown }.map { it.toEvent() }

    /**
     * Sends a snapshot of the queue. Each send returns the HTTP code or throws
     * IOException. A nag's shown row always goes before its events, even if an
     * event was queued first (a tap racing the worker). Stops at the first
     * retryable failure, so a pending shown row holds its events back. A shown row
     * refused with 400 or 404 is dropped with all of its events.
     * Returns true when something is left that is worth retrying.
     */
    suspend fun drain(
        sendShown: suspend (LogMessageRequestDto) -> Int,
        sendEvent: suspend (MessageEventRequestDto) -> Int
    ): Boolean {
        val snapshot = pending()
        val done = mutableListOf<Item>()
        val droppedNags = mutableSetOf<String>()
        var retry = false
        for (item in shownFirst(snapshot)) {
            if (!item.isShown && item.client_ref in droppedNags) {
                done.add(item)
                continue
            }
            val outcome = try {
                outcomeFor(if (item.isShown) sendShown(item.toShown()) else sendEvent(item.toEvent()))
            } catch (e: IOException) {
                Outcome.RETRY
            }
            if (outcome == Outcome.RETRY) {
                retry = true
                break
            }
            done.add(item)
            if (item.isShown && outcome == Outcome.DROP) item.client_ref?.let { droppedNags.add(it) }
        }
        if (done.isNotEmpty() || droppedNags.isNotEmpty()) synchronized(LOCK) {
            val remaining = load().toMutableList()
            done.forEach { remaining.remove(it) }
            // Events queued during this pass for a refused nag go with it.
            remaining.removeAll { !it.isShown && it.client_ref in droppedNags }
            save(remaining)
        }
        return retry
    }

    private fun add(item: Item) = synchronized(LOCK) {
        val items = load().toMutableList()
        items.add(item)
        while (items.size > cap) {
            // Evict the oldest whole nag; an item without a ref is its own nag.
            val oldest = items.first()
            if (oldest.client_ref == null) items.removeAt(0)
            else items.removeAll { it.client_ref == oldest.client_ref }
        }
        save(items)
    }

    private fun load(): List<Item> {
        val json = store.read() ?: return emptyList()
        return try {
            gson.fromJson(json, Array<Item>::class.java)?.filterNotNull()?.toList() ?: emptyList()
        } catch (e: JsonParseException) {
            emptyList()
        }
    }

    private fun save(items: List<Item>) = store.write(gson.toJson(items))

    companion object {
        const val DEFAULT_CAP = 200

        private const val KIND_SHOWN = "shown"
        private const val KIND_EVENT = "event"

        private val LOCK = Any()
        private val gson = Gson()

        private const val PREFS = "mecris_message_events"
        private const val KEY = "queue"

        /**
         * 2xx is DONE (201 inserted; 200 already logged or recorded, idempotent).
         * 404 (unknown nag) and 400 (bad body) are DROP: resending can't help.
         * Everything else (401 expired token, 429, 5xx) is RETRY.
         */
        fun outcomeFor(code: Int): Outcome = when {
            code in 200..299 -> Outcome.DONE
            code == 404 || code == 400 -> Outcome.DROP
            else -> Outcome.RETRY
        }

        /** Shown rows move ahead of their own events; otherwise queue order. */
        internal fun shownFirst(items: List<Item>): List<Item> {
            val shownByRef = items.filter { it.isShown && it.client_ref != null }.associateBy { it.client_ref }
            val emitted = mutableSetOf<Item>()
            val out = mutableListOf<Item>()
            for (item in items) {
                if (!item.isShown) {
                    val shown = shownByRef[item.client_ref]
                    if (shown != null && emitted.add(shown)) out.add(shown)
                    out.add(item)
                } else if (emitted.add(item)) {
                    out.add(item)
                }
            }
            return out
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
