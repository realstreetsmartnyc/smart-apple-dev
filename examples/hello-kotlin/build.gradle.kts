// Repository required for Firebase and Kotlin Multiplatform dependencies.
repositories {
    google()
    mavenCentral()
}

// smart-apple-dev Kotlin Multiplatform template — iOS + Android in one codebase.
// Sources live in src/commonMain (shared) and are compiled to:
//   - Android (com.android.application)
//   - iOS arm64 device   (Kotlin/Native)
//
// Build:
//   ./gradlew assembleDebug                     # Android APK
//   ./gradlew assembleRelease                   # Android AAB-ready release APK
//   ./gradlew linkDebugExecutableIosArm64       # iOS device binary
//   smart-apple-dev build --target android      # orchestrated by smart-apple-dev
//   smart-apple-dev build --target ios          # ditto

plugins {
    kotlin("multiplatform") version "1.9.20"
    id("com.android.application")
    id("com.google.gms.google-services")
}

kotlin {
    // Android target — required so KMP knows about the Android source set
    androidTarget {
        compilations.all {
            kotlinOptions {
                jvmTarget = "17"
            }
        }
    }

    // iOS device target (Kotlin/Native)
    iosArm64 {
        binaries {
            executable {
                entryPoint = "main"
            }
        }
    }

    // Bridge Android's java.srcDirs into the KMP androidMain source set so
    // users can drop .kt files into src/commonMain (shared) or
    // src/androidMain (Android-only) without extra configuration.
    sourceSets {
        val commonMain by getting
        val androidMain by getting
        val iosArm64Main by getting
    }
}

android {
    namespace = "com.example.hello-kotlin"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.example.hello-kotlin"
        minSdk = 21
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    // Point Gradle at the KMP-aware common source so `assembleDebug` picks up
    // src/commonMain/kotlin/ out of the box.
    sourceSets["main"].java.srcDirs("src/commonMain/kotlin")
}

dependencies {
    // Import the Firebase BoM
    implementation(platform("com.google.firebase:firebase-bom:34.18.0"))

    // Firebase products
    implementation("com.google.firebase:firebase-analytics")
    implementation("com.google.firebase:firebase-auth")
    implementation("com.google.firebase:firebase-firestore")
    implementation("com.google.firebase:firebase-storage")
    implementation("com.google.firebase:firebase-messaging")
    implementation("com.google.firebase:firebase-database")

    // Kotlin Multiplatform dependencies (visible to all source sets)
    "commonMainImplementation"("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")
    "commonMainImplementation"("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.0")
}
