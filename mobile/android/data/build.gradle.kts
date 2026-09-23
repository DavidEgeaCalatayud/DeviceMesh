plugins { id("com.android.library"); id("org.jetbrains.kotlin.android") }
android { namespace = "io.github.davidegeacalatayud.devicemesh.data"; compileSdk = 35; defaultConfig { minSdk = 26 }; compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 } }
dependencies { implementation(project(":domain")); implementation(project(":core:model")); implementation(project(":core:network")) }
