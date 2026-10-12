plugins { id("com.android.application"); id("org.jetbrains.kotlin.android"); id("org.jetbrains.kotlin.plugin.compose"); id("com.github.triplet.play") }
if (file("google-services.json").exists()) {
    apply(plugin = "com.google.gms.google-services")
}
android { namespace = "io.github.davidegeacalatayud.devicemesh"; compileSdk = 35
    defaultConfig {
        applicationId = "io.github.davidegeacalatayud.devicemesh"
        minSdk = 26
        targetSdk = 35
        versionCode = System.getenv("DEVICEMESH_ANDROID_VERSION_CODE")?.toIntOrNull() ?: 1
        versionName = System.getenv("DEVICEMESH_ANDROID_VERSION_NAME") ?: "0.1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    buildFeatures { compose = true }
    signingConfigs {
        create("release") {
            val keystorePath = System.getenv("DEVICEMESH_ANDROID_KEYSTORE_PATH")
            if (!keystorePath.isNullOrBlank()) {
                storeFile = file(keystorePath)
                storePassword = System.getenv("DEVICEMESH_ANDROID_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("DEVICEMESH_ANDROID_KEY_ALIAS")
                keyPassword = System.getenv("DEVICEMESH_ANDROID_KEY_PASSWORD")
            }
        }
    }
    buildTypes {
        getByName("release") {
            if (!System.getenv("DEVICEMESH_ANDROID_KEYSTORE_PATH").isNullOrBlank()) {
                signingConfig = signingConfigs.getByName("release")
            }
            isMinifyEnabled = false
        }
    }
}
dependencies {
    implementation(project(":core:model")); implementation(project(":core:network")); implementation(project(":core:designsystem")); implementation(project(":feature:dashboard"))
    implementation(platform("androidx.compose:compose-bom:2024.12.01")); implementation(platform("com.google.firebase:firebase-bom:35.0.0")); implementation("com.google.firebase:firebase-messaging"); implementation("androidx.core:core-ktx:1.15.0"); implementation("androidx.activity:activity-compose:1.10.0"); implementation("androidx.compose.material3:material3"); implementation("androidx.compose.ui:ui"); implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7"); implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    androidTestImplementation(platform("androidx.compose:compose-bom:2024.12.01"))
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test:runner:1.6.2")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}

play {
    track.set("internal")
    defaultToAppBundles.set(true)
}
