pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

plugins {
    id("com.android.application") version "8.2.2" apply false
    id("org.jetbrains.kotlin.android") version "1.9.20" apply false
    id("org.jetbrains.kotlin.jvm") version "1.9.20" apply false
    id("org.jetbrains.kotlin.multiplatform") version "1.9.20" apply false
    id("com.google.gms.google-services") version "4.5.0" apply false
}

rootProject.name = "{{NAME}}"