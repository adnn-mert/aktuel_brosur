package dev.aktuelbrosur.aktuel_brosur

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        createNewBrochuresChannel()
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        // Must match PlatformSystemSettingsOpener.channel in lib/data/notifications.dart.
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, SETTINGS_CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "openNotificationSettings" -> result.success(openNotificationSettings())
                    else -> result.notImplemented()
                }
            }
    }

    // The app's own notification page where the system has one (Android 8+), else its app
    // details page, from which notifications are one tap away.
    private fun openNotificationSettings(): Boolean {
        val intents = mutableListOf<Intent>()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            intents += Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                .putExtra(Settings.EXTRA_APP_PACKAGE, packageName)
        }
        intents += Intent(
            Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
            Uri.fromParts("package", packageName, null),
        )
        for (intent in intents) {
            try {
                startActivity(intent)
                return true
            } catch (e: ActivityNotFoundException) {
                // Some vendor builds lack a page; try the next one.
            } catch (e: SecurityException) {
                // Same.
            }
        }
        return false
    }

    // The scraper's FCM messages name this channel (scraper/notify.py). It must exist before the
    // first one arrives; the user can only turn notifications on from inside the app, so creating
    // it at launch is early enough. Creating an existing channel again is a no-op.
    private fun createNewBrochuresChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            getString(R.string.new_brochures_channel_id),
            getString(R.string.new_brochures_channel_name),
            NotificationManager.IMPORTANCE_HIGH,
        )
        getSystemService(NotificationManager::class.java)?.createNotificationChannel(channel)
    }

    private companion object {
        const val SETTINGS_CHANNEL = "dev.aktuelbrosur.aktuel_brosur/system_settings"
    }
}
