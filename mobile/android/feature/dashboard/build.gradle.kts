plugins { id("com.android.library"); id("org.jetbrains.kotlin.android"); id("org.jetbrains.kotlin.plugin.compose") }
android { namespace = "io.github.davidegeacalatayud.devicemesh.feature.dashboard"; compileSdk = 35; defaultConfig { minSdk = 26 }; buildFeatures { compose = true } }
dependencies { implementation(project(":core:designsystem")); implementation(platform("androidx.compose:compose-bom:2024.12.01")); implementation("androidx.compose.material3:material3"); implementation("androidx.compose.ui:ui") }
