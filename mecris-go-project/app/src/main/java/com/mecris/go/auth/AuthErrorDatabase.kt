package com.mecris.go.auth

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(
    entities = [AuthErrorRecord::class],
    version = 1,
    exportSchema = false
)
abstract class AuthErrorDatabase : RoomDatabase() {
    abstract fun authErrorDao(): AuthErrorDao

    companion object {
        @Volatile
        private var INSTANCE: AuthErrorDatabase? = null

        fun getDatabase(context: Context): AuthErrorDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    AuthErrorDatabase::class.java,
                    "auth_error_database"
                )
                    .addMigrations(MIGRATION_1_2)
                    .fallbackToDestructiveMigration()
                    .build()
                INSTANCE = instance
                instance
            }
        }

        // Future migrations go here
        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(database: SupportSQLiteDatabase) {
                // Add columns if needed
            }
        }
    }
}