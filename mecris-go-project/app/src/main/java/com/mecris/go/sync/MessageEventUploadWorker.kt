package com.mecris.go.sync

import android.content.Context
import android.util.Log
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.mecris.go.BackendManager
import com.mecris.go.auth.PocketIdAuthRepository
import java.util.concurrent.TimeUnit

/**
 * Drains [MessageEventQueue] (#363 phase 1): each nag's shown row to
 * POST /internal/log-message first, then its events to POST /internal/log-message-event,
 * with the same PocketID bearer the other workers use. Network-constrained, with
 * exponential backoff; a retryable failure leaves the rest of the queue in place.
 */
class MessageEventUploadWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : CoroutineWorker(appContext, workerParams) {

    override suspend fun doWork(): Result = try {
        upload()
    } catch (e: kotlinx.coroutines.CancellationException) {
        throw e
    } catch (e: Exception) {
        Log.w(TAG, "Nag event upload failed: ${e.javaClass.simpleName}")
        Result.retry()
    }

    private suspend fun upload(): Result {
        val queue = MessageEventQueue.forContext(applicationContext)
        if (queue.pending().isEmpty()) return Result.success()

        val token = PocketIdAuthRepository.getInstance(applicationContext).getAccessTokenSuspend()
        if (token == null) {
            Log.i(TAG, "No token yet; nag events stay queued")
            return Result.retry()
        }
        val api = SyncServiceApi.create(BackendManager.getBaseUrl(applicationContext))
        val retry = queue.drain(
            sendShown = { shown ->
                val code = api.logMessage("Bearer $token", shown).code()
                // Type and HTTP code only: never the token or message text.
                Log.d(TAG, "Nag shown row ${shown.type}: HTTP $code")
                code
            },
            sendEvent = { event ->
                val code = api.logMessageEvent("Bearer $token", event).code()
                Log.d(TAG, "Nag event ${event.event}: HTTP $code")
                code
            }
        )
        Log.i(TAG, "Nag event upload done; ${queue.pending().size} left, retry=$retry")
        return if (retry) Result.retry() else Result.success()
    }

    companion object {
        private const val TAG = "MessageEventUpload"
        private const val UNIQUE_NAME = "message_event_upload"

        fun schedule(context: Context) {
            val request = OneTimeWorkRequestBuilder<MessageEventUploadWorker>()
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build()
            // APPEND_OR_REPLACE: an event queued while an upload runs still gets a
            // later pass, instead of being skipped by KEEP.
            WorkManager.getInstance(context.applicationContext)
                .enqueueUniqueWork(UNIQUE_NAME, ExistingWorkPolicy.APPEND_OR_REPLACE, request)
        }
    }
}
