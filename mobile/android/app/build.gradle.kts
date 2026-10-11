plugins { id("com.android.application"); id("org.jetbrains.kotlin.android"); id("org.jetbrains.kotlin.plugin.compose") }
android { namespace = "io.github.davidegeacalatayud.devicemesh"; compileSdk = 35
    defaultConfig { applicationId = "io.github.davidegeacalatayud.devicemesh"; minSdk = 26; targetSdk = 35; versionCode = 1; versionName = "0.1.0" }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    buildFeatures { compose = true }
}
dependencies {
    implementation(project(":core:model")); implementation(project(":core:network")); implementation(project(":core:designsystem")); implementation(project(":feature:dashboard"))
    implementation(platform("androidx.compose:compose-bom:2024.12.01")); implementation("androidx.activity:activity-compose:1.10.0"); implementation("androidx.compose.material3:material3"); implementation("androidx.compose.ui:ui"); implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7"); implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
}
