package com.mecris.go.sync

/** Durable local queue of phone nag events (#363 phase 1). */
class MessageEventQueue(private val store: Store, private val cap: Int = DEFAULT_CAP) {

    interface Store {
        fun read(): String?
        fun write(json: String)
    }

    enum class Outcome { DROP, RETRY }

    fun enqueue(event: MessageEventRequestDto) {}

    fun pending(): List<MessageEventRequestDto> = emptyList()

    suspend fun drain(send: suspend (MessageEventRequestDto) -> Int): Boolean = false

    companion object {
        const val DEFAULT_CAP = 200
        fun outcomeFor(code: Int): Outcome = Outcome.RETRY
    }
}
