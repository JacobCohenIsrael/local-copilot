plugins {
    java
    id("org.jetbrains.intellij.platform") version "2.18.1"
}
group = "dev.localcopilot"
version = "0.1.1"
repositories {
    mavenCentral()
    intellijPlatform { defaultRepositories() }
}
dependencies {
    intellijPlatform { webstorm("2026.2.1") }
}
java { sourceCompatibility = JavaVersion.VERSION_21; targetCompatibility = JavaVersion.VERSION_21 }
intellijPlatform {
    pluginConfiguration { ideaVersion { sinceBuild = "261"; untilBuild = "262.*" } }
}
