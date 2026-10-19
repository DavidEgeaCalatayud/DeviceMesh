plugins { id("com.android.library"); id("org.jetbrains.kotlin.android") }
android { namespace = "io.github.davidegeacalatayud.devicemesh.core.network"; compileSdk = 35; defaultConfig { minSdk = 26 }; compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 } }
dependencies {
    implementation(project(":core:model"))
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.11.0")
    testImplementation("junit:junit:4.13.2")
}
