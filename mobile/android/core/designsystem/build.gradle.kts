plugins { id("com.android.library"); id("org.jetbrains.kotlin.android"); id("org.jetbrains.kotlin.plugin.compose") }
android { namespace = "io.github.davidegeacalatayud.devicemesh.core.designsystem"; compileSdk = 35; defaultConfig { minSdk = 26 }; compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }; buildFeatures { compose = true } }
dependencies { implementation(platform("androidx.compose:compose-bom:2026.09.00")); implementation("androidx.compose.material3:material3") }
