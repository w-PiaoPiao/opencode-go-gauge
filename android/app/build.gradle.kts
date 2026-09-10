import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("org.jetbrains.kotlin.plugin.serialization")
    id("com.google.devtools.ksp")
}

android {
    namespace = "io.github.yphyphyph.gogauge"
    compileSdk = 36
    buildToolsVersion = "36.0.0"

    defaultConfig {
        applicationId = "io.github.yphyphyph.gogauge"
        minSdk = 26
        targetSdk = 36
        versionCode = 7
        versionName = "2.1.0d"
    }

    // Debug keystore lives in the workspace (~/.android not writable in this env)
    signingConfigs {
        getByName("debug") {
            storeFile = rootProject.file("debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
        // 正式发布签名: 根目录提供 keystore.properties (gitignored) 时启用,
        // 避免公开仓库 keystore 签名 release (任何人可伪造同签名覆盖安装).
        // 文件格式: storeFile=/abs/path/release.keystore / storePassword=... /
        //           keyAlias=... / keyPassword=...
        if (rootProject.file("keystore.properties").exists()) {
            val keystoreProps = Properties().apply {
                rootProject.file("keystore.properties").inputStream().use { load(it) }
            }
            create("release") {
                storeFile = rootProject.file(keystoreProps.getProperty("storeFile"))
                storePassword = keystoreProps.getProperty("storePassword")
                keyAlias = keystoreProps.getProperty("keyAlias")
                keyPassword = keystoreProps.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            // R8 开启: 缩代码 + 资源压缩. kotlinx.serialization 与 Room 由各自
            // 插件生成 keep 规则, proguard-rules.pro 只需补反射/序列化相关例外.
            isMinifyEnabled = true
            isShrinkResources = true
            // 有 keystore.properties 时用正式签名, 否则回退 debug keystore (个人侧载/CI).
            // 注意: 换签名后无法覆盖安装旧版本, 需先卸载.
            signingConfig = if (signingConfigs.names.contains("release")) {
                signingConfigs.getByName("release")
            } else {
                // 仓库 CI 就是按"个人侧载 + 仓库内 debug.keystore"设计的
                // (见 .github/workflows/release-android.yml), 因此这里不直接 fail
                // 以免打断既有发布流程; 改为显式告警 + 提供严格开关.
                // 上架/公开分发时设 -Pgogauge.strictSigning=true 让构建失败,
                // 强制提供正式 keystore.
                if (project.findProperty("gogauge.strictSigning") == "true") {
                    throw GradleException(
                        "release 构建缺少 keystore.properties: 拒绝用 debug keystore 签名分发产物. " +
                            "请提供正式 keystore, 或去掉 -Pgogauge.strictSigning=true (仅限个人侧载)."
                    )
                }
                logger.warn(
                    "⚠️  release 使用仓库内 debug.keystore 签名 (个人侧载模式). " +
                        "任何持有该密钥的人都能伪造同包名更新; 正式分发请提供 keystore.properties."
                )
                signingConfigs.getByName("debug")
            }
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2025.05.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    debugImplementation("androidx.compose.ui:ui-tooling")

    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.9.1")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.1")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.9.1")
    implementation("androidx.navigation:navigation-compose:2.8.9")

    // Room
    implementation("androidx.room:room-runtime:2.7.2")
    implementation("androidx.room:room-ktx:2.7.2")
    ksp("androidx.room:room-compiler:2.7.2")

    // Network
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    // Serialization
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.1")

    // WorkManager (background sync)
    implementation("androidx.work:work-runtime-ktx:2.10.0")

    // Charts (MPAndroidChart via JitPack)
    implementation("com.github.PhilJay:MPAndroidChart:v3.1.0")

    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")

    // Tests
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.10.2")
    androidTestImplementation(platform("androidx.compose:compose-bom:2025.05.01"))
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
}
