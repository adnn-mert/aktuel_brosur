/// "New brochure" push notifications (Firebase Cloud Messaging, topics).
///
/// The scraper sends one message per chain to the topic `chain-<chainId>`
/// when that chain publishes something new. While notifications are on, the
/// app keeps exactly the favourite chains' topics subscribed. No device token
/// leaves the phone; there is no server of our own.
///
/// Firebase is configured from four `--dart-define` values (see
/// [firebaseOptionsFromEnvironment]); without them the feature is
/// [NotificationsStatus.unavailable] and nothing touches Firebase. Firebase
/// sits behind [PushMessaging] so tests use a fake.
library;

import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart' show MethodChannel;
import 'package:flutter/widgets.dart' show AppLifecycleListener;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'providers.dart';

/// FCM topic of one chain; must match `scraper/notify.py`.
String notificationTopicForChain(String chainId) => 'chain-$chainId';

/// Android notification channel used by the scraper's messages; created in
/// `MainActivity.kt` with the name "Yeni broşürler".
const String newBrochuresChannelId = 'new_brochures';

/// Firebase options from `--dart-define` (or `--dart-define-from-file`);
/// null when any of the four values is missing.
FirebaseOptions? firebaseOptionsFromEnvironment() => firebaseOptionsFrom(
  apiKey: const String.fromEnvironment('FIREBASE_API_KEY'),
  appId: const String.fromEnvironment('FIREBASE_APP_ID'),
  messagingSenderId: const String.fromEnvironment(
    'FIREBASE_MESSAGING_SENDER_ID',
  ),
  projectId: const String.fromEnvironment('FIREBASE_PROJECT_ID'),
);

/// [FirebaseOptions] when every value is non-blank, else null.
@visibleForTesting
FirebaseOptions? firebaseOptionsFrom({
  required String apiKey,
  required String appId,
  required String messagingSenderId,
  required String projectId,
}) {
  final values = [apiKey, appId, messagingSenderId, projectId];
  if (values.any((v) => v.trim().isEmpty)) return null;
  return FirebaseOptions(
    apiKey: apiKey.trim(),
    appId: appId.trim(),
    messagingSenderId: messagingSenderId.trim(),
    projectId: projectId.trim(),
  );
}

/// What the OS says about showing notifications.
enum PushPermission { granted, denied, notDetermined }

/// The user tapped a notification (app in the background or launched by it).
///
/// Every instance is a distinct event ([sequence]; no value equality): two
/// taps on the same notification must both reach listeners, and Riverpod
/// drops a new value that is `==` to the previous one.
@immutable
class NotificationTap {
  NotificationTap({required this.chainId, this.brochureId})
    : sequence = _nextSequence++;

  static int _nextSequence = 0;

  /// Reads the message's data payload (`chain_id`, `brochure_id`); null when
  /// `chain_id` is missing, e.g. a message not sent by our scraper.
  static NotificationTap? fromData(Map<String, dynamic> data) {
    final chainId = data['chain_id'];
    if (chainId is! String || chainId.trim().isEmpty) return null;
    final brochureId = data['brochure_id'];
    return NotificationTap(
      chainId: chainId.trim(),
      brochureId: brochureId is String && brochureId.trim().isNotEmpty
          ? brochureId.trim()
          : null,
    );
  }

  /// Chain to open.
  final String chainId;

  /// Newest new brochure of that chain; null if the message had none. It may
  /// have disappeared from the catalog since (`brochureProvider` gives null).
  final String? brochureId;

  /// Increases with every tap created in this app session.
  final int sequence;

  /// Same chain and brochure (equality itself is identity, see above).
  bool sameTarget(NotificationTap other) =>
      other.chainId == chainId && other.brochureId == brochureId;

  @override
  String toString() => 'NotificationTap#$sequence($chainId, $brochureId)';
}

/// The slice of Firebase Messaging the app uses.
abstract interface class PushMessaging {
  /// Current permission without asking the user.
  Future<PushPermission> permission();

  /// Asks the OS (Android 13+ dialog, iOS dialog) unless already decided.
  Future<PushPermission> requestPermission();

  Future<void> subscribeToTopic(String topic);

  Future<void> unsubscribeFromTopic(String topic);

  /// Off until the user turns notifications on, so the app registers with
  /// FCM only after consent.
  Future<void> setAutoInitEnabled(bool enabled);

  /// The notification that launched the app, if any (consumed once).
  Future<NotificationTap?> initialTap();

  /// Taps on notifications while the app was in the background.
  Stream<NotificationTap> get taps;
}

/// [PushMessaging] on top of `firebase_messaging`.
class FirebasePushMessaging implements PushMessaging {
  FirebasePushMessaging([FirebaseMessaging? messaging])
    : _messaging = messaging ?? FirebaseMessaging.instance;

  final FirebaseMessaging _messaging;

  static PushPermission _map(NotificationSettings settings) =>
      switch (settings.authorizationStatus) {
        AuthorizationStatus.authorized ||
        AuthorizationStatus.provisional => PushPermission.granted,
        AuthorizationStatus.denied ||
        AuthorizationStatus.deniedPermanently => PushPermission.denied,
        AuthorizationStatus.notDetermined => PushPermission.notDetermined,
      };

  @override
  Future<PushPermission> permission() async =>
      _map(await _messaging.getNotificationSettings());

  @override
  Future<PushPermission> requestPermission() async =>
      _map(await _messaging.requestPermission());

  @override
  Future<void> subscribeToTopic(String topic) =>
      _messaging.subscribeToTopic(topic);

  @override
  Future<void> unsubscribeFromTopic(String topic) =>
      _messaging.unsubscribeFromTopic(topic);

  @override
  Future<void> setAutoInitEnabled(bool enabled) =>
      _messaging.setAutoInitEnabled(enabled);

  @override
  Future<NotificationTap?> initialTap() async {
    final message = await _messaging.getInitialMessage();
    return message == null ? null : NotificationTap.fromData(message.data);
  }

  @override
  Stream<NotificationTap> get taps => FirebaseMessaging.onMessageOpenedApp
      .map((m) => NotificationTap.fromData(m.data))
      .where((t) => t != null)
      .cast<NotificationTap>();
}

/// Initialises Firebase from [firebaseOptionsFromEnvironment]. Null (feature
/// unavailable) without configuration, on platforms other than Android/iOS,
/// or when initialisation fails. Never throws.
Future<PushMessaging?> initFirebasePushMessaging({
  FirebaseOptions? options,
}) async {
  final resolved = options ?? firebaseOptionsFromEnvironment();
  if (resolved == null || kIsWeb) return null;
  if (defaultTargetPlatform != TargetPlatform.android &&
      defaultTargetPlatform != TargetPlatform.iOS) {
    return null;
  }
  try {
    await Firebase.initializeApp(options: resolved);
    return FirebasePushMessaging();
  } on Object catch (error) {
    debugPrint('Firebase unavailable: $error');
    return null;
  }
}

/// Firebase Messaging, or null when notifications are unavailable. Tests
/// override it with a fake (or `null`).
final pushMessagingProvider = FutureProvider<PushMessaging?>(
  (ref) => initFirebasePushMessaging(),
);

/// Opens the phone's notification settings page of this app.
abstract interface class SystemSettingsOpener {
  /// True when a settings page was opened; false where unsupported.
  Future<bool> openNotificationSettings();
}

/// Android: a method channel to `MainActivity.kt` (the app's notification
/// settings, falling back to its app details page). iOS: the `app-settings:`
/// URL (this app's page in Settings). Other platforms: false.
class PlatformSystemSettingsOpener implements SystemSettingsOpener {
  PlatformSystemSettingsOpener({
    this.platform,
    Future<bool> Function(Uri uri)? launch,
  }) : _launch = launch ?? _launchExternal;

  /// Must match `MainActivity.kt`.
  static const MethodChannel channel = MethodChannel(
    'dev.aktuelbrosur.aktuel_brosur/system_settings',
  );

  /// Platform to behave as; null means the one the app runs on.
  final TargetPlatform? platform;
  final Future<bool> Function(Uri uri) _launch;

  static Future<bool> _launchExternal(Uri uri) =>
      launchUrl(uri, mode: LaunchMode.externalApplication);

  @override
  Future<bool> openNotificationSettings() async {
    if (kIsWeb) return false;
    try {
      switch (platform ?? defaultTargetPlatform) {
        case TargetPlatform.android:
          return await channel.invokeMethod<bool>('openNotificationSettings') ??
              false;
        case TargetPlatform.iOS:
          return await _launch(Uri.parse('app-settings:'));
        default:
          return false;
      }
    } on Object catch (error) {
      debugPrint('Opening notification settings failed: $error');
      return false;
    }
  }
}

final systemSettingsOpenerProvider = Provider<SystemSettingsOpener>(
  (ref) => PlatformSystemSettingsOpener(),
);

/// Emits each time the app comes back to the foreground (e.g. from the
/// phone's settings). Tests override it with their own stream.
final appResumedProvider = Provider<Stream<void>>((ref) {
  final controller = StreamController<void>.broadcast();
  final listener = AppLifecycleListener(onResume: () => controller.add(null));
  ref.onDispose(() {
    listener.dispose();
    controller.close();
  });
  return controller.stream;
});

/// Persists the on/off choice and which chain topics are subscribed.
abstract interface class NotificationsStore {
  Future<bool> readEnabled();

  Future<void> writeEnabled(bool enabled);

  /// Chain ids whose topic is (as far as we know) subscribed.
  Future<Set<String>> readSubscribed();

  Future<void> writeSubscribed(Set<String> chainIds);
}

/// [NotificationsStore] on top of `shared_preferences`.
class PrefsNotificationsStore implements NotificationsStore {
  PrefsNotificationsStore({Future<SharedPreferences> Function()? prefs})
    : _prefs = prefs ?? SharedPreferences.getInstance;

  static const String enabledKey = 'notifications_enabled';
  static const String subscribedKey = 'notification_subscribed_chain_ids';

  final Future<SharedPreferences> Function() _prefs;

  @override
  Future<bool> readEnabled() async =>
      (await _prefs()).getBool(enabledKey) ?? false;

  @override
  Future<void> writeEnabled(bool enabled) async {
    await (await _prefs()).setBool(enabledKey, enabled);
  }

  @override
  Future<Set<String>> readSubscribed() async =>
      Set.unmodifiable((await _prefs()).getStringList(subscribedKey) ?? []);

  @override
  Future<void> writeSubscribed(Set<String> chainIds) async {
    await (await _prefs()).setStringList(
      subscribedKey,
      chainIds.toList()..sort(),
    );
  }
}

/// In-memory [NotificationsStore] for tests and previews.
class MemoryNotificationsStore implements NotificationsStore {
  MemoryNotificationsStore({this.enabled = false, Set<String>? subscribed})
    : subscribed = {...?subscribed};

  bool enabled;
  final Set<String> subscribed;

  @override
  Future<bool> readEnabled() async => enabled;

  @override
  Future<void> writeEnabled(bool value) async => enabled = value;

  @override
  Future<Set<String>> readSubscribed() async => Set.unmodifiable(subscribed);

  @override
  Future<void> writeSubscribed(Set<String> chainIds) async {
    subscribed
      ..clear()
      ..addAll(chainIds);
  }
}

final notificationsStoreProvider = Provider<NotificationsStore>(
  (ref) => PrefsNotificationsStore(),
);

enum NotificationsStatus {
  /// Firebase is not configured in this build (or failed to start).
  unavailable,

  /// The user has not turned notifications on (the default).
  off,

  /// On: the favourite chains' topics are subscribed and kept in sync.
  on,

  /// The OS refuses notifications (permission denied); only the system
  /// settings can change that.
  blockedBySystem,
}

@immutable
class NotificationsState {
  const NotificationsState(this.status);

  final NotificationsStatus status;

  @override
  bool operator ==(Object other) =>
      other is NotificationsState && other.status == status;

  @override
  int get hashCode => status.hashCode;

  @override
  String toString() => 'NotificationsState(${status.name})';
}

/// How long a topic call may take before it is treated as queued: both
/// Firebase SDKs keep pending topic operations and retry them when online.
const Duration topicOperationTimeout = Duration(seconds: 15);

/// Runs topic changes one after another, in call order, across rebuilds of
/// [NotificationsController].
class _SerialQueue {
  Future<void> _tail = Future.value();

  Future<void> run(Future<void> Function() task) {
    final next = _tail.then((_) => task()).catchError((Object error) {
      debugPrint('Notification topic sync failed: $error');
    });
    _tail = next;
    return next;
  }
}

final _topicQueueProvider = Provider<_SerialQueue>((ref) => _SerialQueue());

/// On/off switch for new-brochure notifications.
class NotificationsController extends AsyncNotifier<NotificationsState> {
  static const _unavailable = NotificationsState(
    NotificationsStatus.unavailable,
  );
  static const _off = NotificationsState(NotificationsStatus.off);
  static const _on = NotificationsState(NotificationsStatus.on);
  static const _blocked = NotificationsState(
    NotificationsStatus.blockedBySystem,
  );

  @override
  Future<NotificationsState> build() async {
    final messaging = await ref.watch(pushMessagingProvider.future);
    if (messaging == null) return _unavailable;
    final store = ref.watch(notificationsStoreProvider);
    final queue = ref.watch(_topicQueueProvider);
    // "Enabled" means the user asked for notifications, whatever the OS said.
    if (!await store.readEnabled()) {
      // Leftovers of a turnOff that could not reach Firebase.
      if ((await store.readSubscribed()).isNotEmpty) {
        unawaited(queue.run(() => _syncTopics(messaging, store, const {})));
      }
      return _off;
    }
    final granted = await messaging.permission() == PushPermission.granted;
    // Back from the phone's settings: allowed there -> finish turning on;
    // revoked there -> blocked. Only a change rebuilds.
    final resumes = ref.watch(appResumedProvider).listen((_) async {
      try {
        final now = await messaging.permission() == PushPermission.granted;
        if (now != granted && ref.mounted) ref.invalidateSelf();
      } on Object catch (error) {
        debugPrint('Re-checking notification permission failed: $error');
      }
    });
    ref.onDispose(resumes.cancel);
    if (!granted) return _blocked;
    unawaited(queue.run(() => messaging.setAutoInitEnabled(true)));
    // Cleared when this "on" build is replaced (turnOff, invalidate), so a
    // queued sync of an old favourites set cannot resubscribe afterwards.
    var active = true;
    ref.onDispose(() => active = false);
    ref.listen<AsyncValue<Set<String>>>(favoritesProvider, (_, next) {
      final favorites = next.value;
      if (favorites == null) return;
      unawaited(
        queue.run(() async {
          if (active) await _syncTopics(messaging, store, favorites);
        }),
      );
    }, fireImmediately: true);
    return _on;
  }

  /// Asks the OS for permission (nothing is asked before this call) and
  /// remembers that the user wants notifications. On grant subscribes the
  /// favourite chains' topics ([NotificationsStatus.on]); on denial the state
  /// is [NotificationsStatus.blockedBySystem] and stays so across restarts
  /// until the permission is given in the phone's settings (then, on return
  /// to the app, turning on completes by itself) or [turnOff] is called.
  /// Completes after the subscriptions were attempted. Never throws; on an
  /// unexpected error the previous state stays.
  Future<void> turnOn() async {
    try {
      final messaging = await ref.read(pushMessagingProvider.future);
      if (messaging == null) {
        if (ref.mounted) state = const AsyncData(_unavailable);
        return;
      }
      await messaging.requestPermission();
      await ref.read(notificationsStoreProvider).writeEnabled(true);
      if (!ref.mounted) return;
      // The rebuild checks the permission and, when granted, starts the
      // favourites listener, which subscribes.
      ref.invalidateSelf();
      await future;
      await ref.read(_topicQueueProvider).run(() async {});
    } on Object catch (error) {
      debugPrint('Turning notifications on failed: $error');
    }
  }

  /// Opens this app's notification settings in the phone's settings (for
  /// [NotificationsStatus.blockedBySystem]). Android: the app's notification
  /// page, else its app details page; iOS: the app's page in Settings. False
  /// when nothing could be opened. Never throws. When the user comes back,
  /// the state refreshes by itself.
  Future<bool> openSystemSettings() async {
    try {
      return await ref
          .read(systemSettingsOpenerProvider)
          .openNotificationSettings();
    } on Object catch (error) {
      debugPrint('Opening notification settings failed: $error');
      return false;
    }
  }

  /// Unsubscribes every chain topic and remembers "off". Completes after the
  /// unsubscriptions were attempted. Never throws.
  Future<void> turnOff() async {
    try {
      final messaging = await ref.read(pushMessagingProvider.future);
      if (messaging == null) {
        if (ref.mounted) state = const AsyncData(_unavailable);
        return;
      }
      final store = ref.read(notificationsStoreProvider);
      final queue = ref.read(_topicQueueProvider);
      final favorites = ref.read(favoritesProvider).value ?? const <String>{};
      await store.writeEnabled(false);
      if (!ref.mounted) return;
      // Ends the "on" build and its favourites listener.
      ref.invalidateSelf();
      state = const AsyncData(_off);
      // Favourites too: a subscription may have gone out without being
      // recorded (the app was stopped in between).
      await queue.run(
        () => _syncTopics(messaging, store, const {}, alsoRemove: favorites),
      );
      await messaging.setAutoInitEnabled(false);
    } on Object catch (error) {
      debugPrint('Turning notifications off failed: $error');
    }
  }
}

/// Subscribes [wanted] and unsubscribes everything else that is recorded as
/// subscribed (plus [alsoRemove]). A failed call leaves that chain as it was
/// so the next sync retries; a call that times out is treated as done
/// (Firebase queues it).
Future<void> _syncTopics(
  PushMessaging messaging,
  NotificationsStore store,
  Set<String> wanted, {
  Set<String> alsoRemove = const {},
}) async {
  final subscribed = {...await store.readSubscribed()};
  final toAdd = wanted.difference(subscribed);
  final toRemove = {
    ...subscribed.difference(wanted),
    ...alsoRemove.difference(wanted),
  };
  for (final chainId in toAdd) {
    if (await _topicCall(
      () => messaging.subscribeToTopic(notificationTopicForChain(chainId)),
    )) {
      subscribed.add(chainId);
    }
  }
  for (final chainId in toRemove) {
    if (await _topicCall(
      () => messaging.unsubscribeFromTopic(notificationTopicForChain(chainId)),
    )) {
      subscribed.remove(chainId);
    }
  }
  if (toAdd.isNotEmpty || toRemove.isNotEmpty) {
    await store.writeSubscribed(subscribed);
  }
}

Future<bool> _topicCall(Future<void> Function() call) async {
  try {
    await call().timeout(topicOperationTimeout);
    return true;
  } on TimeoutException {
    return true;
  } on Object catch (error) {
    debugPrint('Topic call failed: $error');
    return false;
  }
}

/// Notifications on/off. `.notifier.turnOn()` / `.turnOff()`.
final notificationsProvider =
    AsyncNotifierProvider<NotificationsController, NotificationsState>(
      NotificationsController.new,
      retry: (_, _) => null,
    );

/// Emits when the user taps one of our notifications: first the one that
/// launched the app (if any), then taps while the app runs in the
/// background. Listen at the app root (`ref.listen`) from startup so no tap
/// is missed. Never emits when notifications are unavailable.
final notificationTapProvider = StreamProvider<NotificationTap>((ref) async* {
  final messaging = await ref.watch(pushMessagingProvider.future);
  if (messaging == null) return;
  try {
    final initial = await messaging.initialTap();
    if (initial != null) yield initial;
  } on Object catch (error) {
    debugPrint('Reading the launch notification failed: $error');
  }
  yield* messaging.taps;
}, retry: (_, _) => null);
