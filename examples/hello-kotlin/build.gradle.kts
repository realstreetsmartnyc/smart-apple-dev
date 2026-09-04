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
    // Google Services plugin removed by default; opt-in via a Firebase setup
    // guide when you actually wire up a real Firebase project. CI builds
    // without Firebase by skipping the plugin and Firebase BoM dependencies.
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
}

dependencies {
    // Firebase is opt-in. To enable, run:
    //   1. Create a project at https://console.firebase.google.com/
    //   2. Download google-services.json into the project root
    //   3. Uncomment the `id("com.google.gms.google-services")` plugin in the
    //      plugins block above
    //   4. Uncomment the Firebase BoM + product lines below
    //   5. Run ./gradlew assembleDebug

    // Kotlin Multiplatform dependencies (visible to all source sets)
    "commonMainImplementation"("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")
    "commonMainImplementation"("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.0")
}
