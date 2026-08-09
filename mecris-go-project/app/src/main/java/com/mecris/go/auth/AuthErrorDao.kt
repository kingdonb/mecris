package com.mecris.go.auth

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface AuthErrorDao {

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insert(record: AuthErrorRecord)

    @Query("SELECT * FROM autherrorrecord ORDER BY timestamp DESC LIMIT 100")
    fun getRecentErrors(): Flow<List<AuthErrorRecord>>

    @Query("SELECT * FROM autherrorrecord WHERE uploaded = 0 ORDER BY timestamp ASC")
    fun getPendingUpload(): Flow<List<AuthErrorRecord>>

    @Query("UPDATE autherrorrecord SET uploaded = 1 WHERE id IN (:ids)")
    suspend fun markAsUploaded(ids: List<Long>)

    @Query("DELETE FROM autherrorrecord WHERE timestamp < :cutoff")
    suspend fun deleteOldErrors(cutoff: Long)
}