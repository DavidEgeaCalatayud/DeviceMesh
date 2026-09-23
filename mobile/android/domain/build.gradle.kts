plugins { id("com.android.library"); id("org.jetbrains.kotlin.android") }
android { namespace = "io.github.davidegeacalatayud.devicemesh.domain"; compileSdk = 35; defaultConfig { minSdk = 26 }; compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 } }
dependencies { implementation(project(":core:model")) }
