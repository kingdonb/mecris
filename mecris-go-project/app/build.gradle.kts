plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "com.mecris.go"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.mecris.go"
        minSdk = 31
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"

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
            useLegacyPackaging = false
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
    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    debugImplementation(libs.androidx.compose.ui.tooling)
    debugImplementation(libs.androidx.compose.ui.test.manifest)

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
}