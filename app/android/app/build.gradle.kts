import java.util.Base64
import java.util.Properties

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

    // The key that signs release APKs. Android only installs an update over an app signed with
    // the same key, so it must stay the same across releases (see releaseSigning() below).
    val signing = releaseSigning()
    if (signing != null) {
        signingConfigs {
            create("release") {
                storeFile = signing.storeFile
                storePassword = signing.storePassword
                keyAlias = signing.keyAlias
                keyPassword = signing.keyPassword
            }
        }
    }

    buildTypes {
        release {
            signingConfig = if (signing != null) {
                signingConfigs.getByName("release")
            } else {
                // Local development only; `flutter run --release` keeps working without a key.
                signingConfigs.getByName("debug")
            }
        }
    }
}

if (releaseSigning() == null) {
    val message = "No release signing key found (ANDROID_KEYSTORE_* environment variables, " +
        "android/key.properties or secrets/android/keystore.properties)."
    gradle.taskGraph.whenReady {
        val buildsRelease = allTasks.any { task ->
            val name = task.name
            task.project == project && name.endsWith("Release") &&
                (name.startsWith("assemble") || name.startsWith("package") || name.startsWith("bundle"))
        }
        if (buildsRelease) {
            // CI must never publish an APK signed with a throwaway debug key: nobody could
            // install it over the previous release.
            if (!System.getenv("CI").isNullOrBlank()) {
                throw GradleException("$message Refusing to sign a CI release with the debug key.")
            }
            logger.warn("WARNING: $message Signing the release build with the DEBUG key; " +
                "this APK cannot update an installed release build.")
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

class ReleaseSigning(
    val storeFile: File,
    val storePassword: String,
    val keyAlias: String,
    val keyPassword: String,
)

// Order: environment variables (CI), android/key.properties, secrets/android/keystore.properties
// (repository root). The last two are git-ignored; a relative storeFile is resolved against the
// folder of the properties file.
fun releaseSigning(): ReleaseSigning? {
    fun env(name: String) = System.getenv(name)?.takeIf { it.isNotBlank() }
    val envPath = env("ANDROID_KEYSTORE_PATH")
    val envStorePassword = env("ANDROID_KEYSTORE_PASSWORD")
    val envAlias = env("ANDROID_KEY_ALIAS")
    val envKeyPassword = env("ANDROID_KEY_PASSWORD")
    if (envPath != null && envStorePassword != null && envAlias != null && envKeyPassword != null) {
        return ReleaseSigning(File(envPath), envStorePassword, envAlias, envKeyPassword)
    }
    val candidates = listOf(
        rootProject.file("key.properties"),
        rootProject.projectDir.resolve("../../secrets/android/keystore.properties").normalize(),
    )
    for (file in candidates.filter { it.isFile }) {
        val props = Properties().apply { file.inputStream().use { load(it) } }
        val store = props.getProperty("storeFile")?.trim().orEmpty()
        val storePassword = props.getProperty("storePassword")?.trim().orEmpty()
        val alias = props.getProperty("keyAlias")?.trim().orEmpty()
        val keyPassword = props.getProperty("keyPassword")?.trim().orEmpty()
        if (store.isEmpty() || storePassword.isEmpty() || alias.isEmpty() || keyPassword.isEmpty()) continue
        val storeFile = File(store).let { if (it.isAbsolute) it else file.parentFile.resolve(it) }
        return ReleaseSigning(storeFile, storePassword, alias, keyPassword)
    }
    return null
}
