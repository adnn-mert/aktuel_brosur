import java.util.Base64

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "dev.aktuelbrosur.aktuel_brosur"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "dev.aktuelbrosur.aktuel_brosur"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName

        // Firebase without google-services.json or its Gradle plugin: the same four
        // --dart-define values the Dart code reads (lib/data/notifications.dart) become the
        // string resources Firebase's own startup reads. That lets FCM start Firebase in a
        // process where Flutter is not running (a message arriving while the app is closed).
        // Without the values nothing is added and notifications are simply unavailable.
        val firebase = firebaseResources(dartDefines())
        if (firebase.isNotEmpty()) {
            firebase.forEach { (name, value) -> resValue("string", name, value) }
        }
    }

    buildFeatures {
        resValues = true
    }

    buildTypes {
        release {
            // TODO: Add your own signing config for the release build.
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}

// The flutter tool passes --dart-define and --dart-define-from-file values as one property:
// comma separated, each entry base64("KEY=value").
fun dartDefines(): Map<String, String> {
    val raw = project.findProperty("dart-defines") as String? ?: return emptyMap()
    return raw.split(",").filter { it.isNotBlank() }.mapNotNull { entry ->
        val decoded = try {
            String(Base64.getDecoder().decode(entry), Charsets.UTF_8)
        } catch (e: IllegalArgumentException) {
            return@mapNotNull null
        }
        val eq = decoded.indexOf('=')
        if (eq <= 0) null else decoded.substring(0, eq) to decoded.substring(eq + 1)
    }.toMap()
}

// Resource names are the ones the google-services plugin would generate.
fun firebaseResources(defines: Map<String, String>): Map<String, String> {
    val resources = mapOf(
        "google_api_key" to defines["FIREBASE_API_KEY"],
        "google_app_id" to defines["FIREBASE_APP_ID"],
        "gcm_defaultSenderId" to defines["FIREBASE_MESSAGING_SENDER_ID"],
        "project_id" to defines["FIREBASE_PROJECT_ID"],
    )
    if (resources.values.any { it.isNullOrBlank() }) return emptyMap()
    return resources.mapValues { it.value!!.trim() }
}
