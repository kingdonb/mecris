# Strategic Roadmap for talktype

## A. Executive Summary

Talktype can absolutely become operationally reliable for daily use. Its current architecture is simple and effective, but brittle. The path to reliability lies not in adopting a complex, distributed streaming architecture like EchoKit, but in systematically hardening the existing local-first, batch-oriented model.

The top risks are data loss from crashes and unrecoverable transcription failures. Both can be solved with local-first persistence.

The essential change is to **move from in-memory audio buffering to incremental disk-based buffering**. This single change is the foundation for all other resilience improvements, including crash recovery and retry mechanisms. We must prioritize determinism and recoverability over the perceived benefits of low-latency streaming, which introduces significant complexity and new failure modes.

## B. EchoKit Insights

EchoKit is a sophisticated, distributed voice agent platform. It is designed for a different problem: a "thin" edge device (like an ESP32) controlling a "thick" cloud-based AI. Our context (a powerful laptop) is fundamentally different.

### Lessons Worth Adopting:

1.  **VAD (Voice Activity Detection):** EchoKit's use of a dedicated VAD service (Silero VAD) to automatically start/stop recording is a major UX improvement. This would be a valuable *optional* mode for `talktype`, reducing the cognitive load of push-to-talk.
2.  **Service-Oriented Thinking:** While we should not adopt EchoKit's distributed architecture, the *idea* of separating concerns is valuable. Our `talktype.py` (client) and `whisper_server.py` (ASR service) is a good start. We should maintain and strengthen this boundary.
3.  **Explicit Protocol:** EchoKit uses a well-defined WebSocket protocol (`protocol.rs`) with distinct server and client events. This is a good practice for ensuring robust communication, even between our local client and server.

### What to Explicitly NOT Adopt:

1.  **Distributed Streaming Pipeline:** EchoKit's core is a pipeline of streams (VAD -> ASR -> LLM -> TTS). The ASR part is still a batch operation on a buffered utterance. The complexity of managing this distributed pipeline is immense and unnecessary for our use case. It introduces multiple points of failure (network, individual service outages) that we can avoid by staying local.
2.  **Reliance on External APIs for Core Transcription:** EchoKit is designed to plug into various ASR/LLM/TTS APIs. `talktype`'s strength is its local-first nature (`faster-whisper`), which makes it deterministic and free from external rate limits or dependencies. We should preserve this.
3.  **Thin Client / Thick Server Model:** We are not building for an ESP32. Our "client" (the laptop) has ample resources. We should leverage this by doing as much as possible locally.

## C. Failure Mode Analysis

### 1. Current `talktype` (Batch Local ASR)

*   **Failure Points:**
    *   **Client Crash:** In-memory audio buffer is lost. **Total data loss.**
    *   **Server Crash:** Transcription fails. Client has no copy of the audio to retry. **Total data loss.**
    *   **Network Error (Client -> Server):** Same as server crash. **Total data loss.**
*   **Root Cause:** Lack of audio persistence.

### 2. Streaming ASR (Hypothetical)

*   **Failure Points:**
    *   **Network Jitter/Drops:** Individual audio chunks lost in transit. May corrupt the entire transcription.
    *   **Server Crash:** In-flight chunks and server-side buffers are lost.
    *   **ASR Engine Failure:** The streaming ASR engine itself might fail on a specific audio pattern, halting the stream.
*   **Root Cause:** The added complexity of managing a continuous stream over a network, with multiple points of failure. Recovery requires complex chunk-level acknowledgments and buffering on both client and server.

### 3. Resilience Improvements with Local Persistence

By saving audio to disk *before* transcription, we fundamentally change the reliability model:

*   **Client Crash:** On restart, the client can detect an orphaned audio file and re-submit it for transcription. **No data loss.**
*   **Server Crash / Network Error:** The client can detect the failure and re-submit the saved audio file. With a simple retry loop, it can wait for the server to come back online. **No data loss.**

## D. Priority Roadmap

This roadmap prioritizes stability and recoverability over new features. Each phase builds a foundation for the next.

### Phase 0 – Hardening (The most critical phase)

*Goal: Eliminate data loss and make the system robust against common failures.*

1.  **Incremental Audio Buffering to Disk:**
    *   Modify `talktype.py` to, upon `start_recording`, create a temporary WAV file.
    *   As audio chunks are received by `audio_callback`, append them directly to this file instead of an in-memory list.
    *   `stop_recording` will now just finalize the WAV file.
2.  **Transactional Transcription:**
    *   The `transcribe_and_paste` thread will now work with a file path instead of an in-memory audio array.
    *   **On successful transcription and pasting, delete the temporary audio file.**
    *   **If transcription fails for any reason (server crash, network error), the audio file is kept.**
3.  **Crash Recovery:**
    *   On startup, `talktype.py` should check a designated temporary directory for any orphaned audio files.
    *   If found, it should prompt the user to transcribe them. This handles the case where the client itself crashes.
4.  **Robust Focus Handling:**
    *   Improve the `paste_text` function to be more resilient to focus changes. Before pasting, re-verify that the target window is still the active one. If not, log an error and preserve the transcribed text in the clipboard.

### Phase 1 – Resilience & UX

*Goal: Build on the hardened foundation to improve the user experience and add more robust recovery.*

1.  **Server-Side Resilience:**
    *   Modify `whisper_server.py` to also save the received audio to a temporary file before processing. This provides a second layer of defense and helps in debugging. The server should have its own cleanup logic.
2.  **Client-Side Retry Mechanism:**
    *   Implement a simple retry loop in `talktype.py`'s `transcribe_api` function. If a request to the server fails, it should wait (e.g., with exponential backoff) and retry a few times before giving up.
3.  **Explicit State Management & UI:**
    *   Improve the terminal title/UI to show more explicit states: `SAVING AUDIO`, `RETRYING...`, `TRANSCRIPTION FAILED (audio saved)`. This gives the user confidence that their data is safe even if something goes wrong.
4.  **Introduce Optional VAD:**
    *   Integrate a local VAD library (like `py-silero-vad-lite`) into `talktype.py`.
    *   Add a `--vad` flag to enable it. In this mode, the client listens continuously, automatically starting/stopping the disk-based recording based on speech activity.

### Phase 2 – Advanced Features (Optional)

*Goal: Explore features that improve latency and workflow, but only after the core system is rock-solid.*

1.  **Chunked Incremental Processing (Hybrid Model):**
    *   Instead of waiting for the full recording to finish, `talktype.py` could be modified to send chunks of the audio file (e.g., every 5 seconds) to the server.
    *   `whisper_server.py` would need to be updated to handle these chunks, transcribe them, and append the results. This is complex, as `faster-whisper` would be reinvoked for each chunk, and the context between chunks would be lost.
    *   **Tradeoff Evaluation:** This would provide faster feedback but would likely decrease accuracy compared to transcribing the full audio at once. This should be implemented as an optional, experimental feature.
2.  **Transcription History/Queue:**
    *   Build a simple UI or command to view a list of recently transcribed (and orphaned) audio files.
    *   Allow the user to re-copy the text from a previous transcription or retry a failed one.

### Phase 3 – Architecture Evolution

*Goal: Consider a more formal architectural separation if the system's complexity warrants it.*

*   This phase is **not recommended** at this time. The current client/server separation is sufficient. Introducing a WebSocket layer or an event bus would add significant complexity for marginal benefit in our local-first context. We should only consider this if we find a compelling reason to move to a more distributed model (e.g., supporting multiple clients), which is not part of the current objective.

## E. Streaming Decision

**Recommendation: Avoid true streaming ASR. Embrace chunked incremental *persistence*.**

*   **Stay Batch-Only (for ASR):** For the core transcription step, we should continue to use `faster-whisper` in batch mode on a complete utterance (or a large chunk). This gives us the best accuracy and leverages the strengths of the existing model.
*   **Implement Chunked Incremental Processing (for Persistence):** The "streaming" we should implement is the incremental writing of audio to a local disk file. This gives us resilience without the complexity of a real-time ASR engine.
*   **Add Optional Streaming (for TTS/LLM output):** If we were to integrate an LLM, adopting EchoKit's model of streaming the *output* (text deltas and TTS audio chunks) would be a great UX improvement. But for the core `talktype` function (speech-to-text), it's not the priority.

**The final recommendation is to implement the hybrid model described in Phase 2 as an optional feature, after fully completing Phases 0 and 1.** The default mode should remain the simple, robust, full-utterance batch processing.

## F. Operational Readiness Score

*   **Current Reliability:** **3/10**. The system works, but the risk of data loss on any failure is too high for it to be considered reliable. A single crash can wipe out an entire thought.
*   **Potential Reliability (after Phase 0 & 1):** **9/10**. With disk-based buffering, crash recovery, and retries, the system would be extremely robust. Data loss would be virtually eliminated, and transcription would be eventual-guaranteed as long as the server is running.

**To be "relied on," the following must be true:**
1.  **No audio data is ever held only in memory.** It must be written to disk before any potentially failing operation (like a network request).
2.  **The system must be able to recover from client and server crashes without losing user recordings.**
3.  **The system must provide clear feedback to the user about its state, especially when errors occur, so they know their data is safe.**

This roadmap provides a clear, incremental path to achieving that level of reliability.
