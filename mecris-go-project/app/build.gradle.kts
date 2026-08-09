plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android") version "2.2.10"
    id("org.jetbrains.kotlin.plugin.compose") version "2.2.10"
    id("org.jetbrains.kotlin.kapt") version "2.2.10"
}

android {
    namespace = "com.mecris.go"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.mecris.go"
        minSdk = 31
        targetSdk = 35
        versionCode = 26
        versionName = "0.0.1-rc.2"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        
        manifestPlaceholders["appAuthRedirectScheme"] = "com.mecris.go"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    buildFeatures {
        compose = true
    }

    packaging {
        jniLibs {
            // Support 16 KB page sizes for Android 15+
            // useLegacyPackaging = false
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.activity:activity-compose:1.8.2")
    implementation(platform("androidx.compose:compose-bom:2024.09.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.1.5")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.5.1")
    androidTestImplementation(platform("androidx.compose:compose-bom:2024.09.00"))
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")

    testImplementation("io.mockk:mockk:1.13.12")

    // AppAuth for OIDC (Pocket ID)
    implementation("net.openid:appauth:0.11.1")

    // Health Connect
    implementation("androidx.health.connect:connect-client:1.1.0-alpha12")

    // Location
    implementation("com.google.android.gms:play-services-location:21.3.0")

    // WorkManager
    implementation("androidx.work:work-runtime-ktx:2.9.0")

    // Credentials (for Passkeys)
    implementation("androidx.credentials:credentials:1.2.0-rc01")
    implementation("androidx.credentials:credentials-play-services-auth:1.2.0-rc01")

    // Retrofit for Beeminder API
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-gson:2.9.0")

    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")

    // Google AI Edge SDK for AICore (On-Device Gemini Nano)
    implementation("com.google.ai.edge.aicore:aicore:0.0.1-exp01")

    // Security: EncryptedSharedPreferences
    implementation("androidx.security:security-crypto:1.1.0-alpha06")

    // Room Database for error telemetry
    implementation("androidx.room:room-runtime:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")
    kapt("androidx.room:room-compiler:2.6.1")

    // Kotlinx datetime for Instant
    implementation("org.jetbrains.kotlinx:kotlinx-datetime:0.6.0")

    // Kotlinx serialization for AuthError
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")

    // Material3 for Snackbar
    implementation("com.google.android.material:material:1.12.0")
}