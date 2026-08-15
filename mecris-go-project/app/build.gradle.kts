plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.ksp)
}

android {
    namespace = "com.mecris.go"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.mecris.go"
        minSdk = 31
        targetSdk = 37
        versionCode = 30
        versionName = "0.0.1-rc.6"

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
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        compose = true
    }
    kotlinOptions {
        jvmTarget = "17"
    }

    packaging {
        jniLibs {
            // Support 16 KB page sizes for Android 15+
            // useLegacyPackaging = false
        }
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons.core)
    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    debugImplementation(libs.androidx.compose.ui.tooling)
    debugImplementation(libs.androidx.compose.ui.test.manifest)

    testImplementation("io.mockk:mockk:1.13.12")

    // AppAuth for OIDC (Pocket ID)
    implementation(libs.appauth)

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
    implementation("com.squareup.retrofit2:retrofit:3.0.0")
    implementation("com.squareup.retrofit2:converter-gson:3.0.0")

    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")

    // Google AI Edge SDK for AICore (On-Device Gemini Nano)
    implementation("com.google.ai.edge.aicore:aicore:0.0.1-exp01")

    // Security: EncryptedSharedPreferences
    implementation(libs.androidx.security.crypto)

    // Room Database for error telemetry
    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)

    // Kotlinx datetime for Instant
    implementation(libs.kotlinx.datetime)

    // Kotlinx serialization for AuthError
    implementation(libs.kotlinx.serialization.json)

    // Material3 for Snackbar
    implementation(libs.material)
}