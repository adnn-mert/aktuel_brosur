import 'dart:async';

import 'package:aktuel_brosur/data/data.dart';
import 'package:flutter/foundation.dart' show TargetPlatform;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class FakePushMessaging implements PushMessaging {
  FakePushMessaging({
    this.current = PushPermission.notDetermined,
    this.answer = PushPermission.granted,
    this.initial,
  });

  PushPermission current;
  PushPermission answer;
  NotificationTap? initial;
  int permissionRequests = 0;
  bool? autoInit;
  final Set<String> topics = {};
  final List<String> calls = [];
  final Set<String> failing = {};
  final StreamController<NotificationTap> tapController =
      StreamController<NotificationTap>.broadcast();

  @override
  Future<PushPermission> permission() async => current;

  @override
  Future<PushPermission> requestPermission() async {
    permissionRequests++;
    current = answer;
    return answer;
  }

  @override
  Future<void> subscribeToTopic(String topic) async {
    calls.add('+$topic');
    if (failing.contains(topic)) throw Exception('offline');
    topics.add(topic);
  }

  @override
  Future<void> unsubscribeFromTopic(String topic) async {
    calls.add('-$topic');
    if (failing.contains(topic)) throw Exception('offline');
    topics.remove(topic);
  }

  @override
  Future<void> setAutoInitEnabled(bool enabled) async => autoInit = enabled;

  @override
  Future<NotificationTap?> initialTap() async {
    final tap = initial;
    initial = null;
    return tap;
  }

  @override
  Stream<NotificationTap> get taps => tapController.stream;
}

/// Lets queued topic work (microtasks and zero-delay timers) finish.
Future<void> settle() async {
  for (var i = 0; i < 20; i++) {
    await Future<void>.delayed(Duration.zero);
  }
}

void main() {
  late FakePushMessaging push;
  late MemoryNotificationsStore store;
  late MemoryFavoritesStore favorites;
  late StreamController<void> resumes;
  late FakeSettingsOpener opener;

  ProviderContainer makeContainer({bool available = true}) {
    final container = ProviderContainer.test(
      overrides: [
        pushMessagingProvider.overrideWith(
          (ref) async => available ? push : null,
        ),
        notificationsStoreProvider.overrideWithValue(store),
        favoritesStoreProvider.overrideWithValue(favorites),
        appResumedProvider.overrideWithValue(resumes.stream),
        systemSettingsOpenerProvider.overrideWithValue(opener),
      ],
    );
    container.listen(notificationsProvider, (_, _) {});
    return container;
  }

  Future<NotificationsStatus> status(ProviderContainer c) async =>
      (await c.read(notificationsProvider.future)).status;

  setUp(() {
    push = FakePushMessaging();
    store = MemoryNotificationsStore();
    favorites = MemoryFavoritesStore(['bim', 'sok']);
    resumes = StreamController<void>.broadcast();
    opener = FakeSettingsOpener();
  });

  tearDown(() => resumes.close());

  group('unavailable', () {
    test('without Firebase nothing is asked and nothing changes', () async {
      final c = makeContainer(available: false);
      expect(await status(c), NotificationsStatus.unavailable);
      await c.read(notificationsProvider.notifier).turnOn();
      expect(await status(c), NotificationsStatus.unavailable);
      await c.read(notificationsProvider.notifier).turnOff();
      expect(
        c.read(notificationsProvider).value?.status,
        NotificationsStatus.unavailable,
      );
      expect(push.permissionRequests, 0);
      expect(push.calls, isEmpty);
      expect(store.enabled, isFalse);
    });

    test('a build without dart-defines has no Firebase options', () async {
      expect(firebaseOptionsFromEnvironment(), isNull);
      expect(await initFirebasePushMessaging(), isNull);
    });

    test('options need all four values', () {
      final options = firebaseOptionsFrom(
        apiKey: ' key ',
        appId: '1:2:android:3',
        messagingSenderId: '2',
        projectId: 'demo',
      );
      expect(options?.apiKey, 'key');
      expect(options?.projectId, 'demo');
      for (final blank in ['apiKey', 'appId', 'sender', 'project']) {
        expect(
          firebaseOptionsFrom(
            apiKey: blank == 'apiKey' ? ' ' : 'k',
            appId: blank == 'appId' ? '' : 'a',
            messagingSenderId: blank == 'sender' ? '' : 's',
            projectId: blank == 'project' ? '' : 'p',
          ),
          isNull,
          reason: blank,
        );
      }
    });
  });

  group('off by default', () {
    test('nothing is requested from the OS until turnOn', () async {
      final c = makeContainer();
      expect(await status(c), NotificationsStatus.off);
      await c.read(favoritesProvider.notifier).toggle('migros');
      await settle();
      expect(push.permissionRequests, 0);
      expect(push.calls, isEmpty);
      expect(push.autoInit, isNull);
    });
  });

  group('turnOn', () {
    test('granted: subscribes the favourite chains and remembers it', () async {
      final c = makeContainer();
      await status(c);
      await c.read(notificationsProvider.notifier).turnOn();
      expect(await status(c), NotificationsStatus.on);
      expect(push.permissionRequests, 1);
      expect(push.topics, {'chain-bim', 'chain-sok'});
      expect(store.enabled, isTrue);
      expect(store.subscribed, {'bim', 'sok'});
      expect(push.autoInit, isTrue);
    });

    test('denied: blocked by the system, nothing subscribed', () async {
      push.answer = PushPermission.denied;
      final c = makeContainer();
      await status(c);
      await c.read(notificationsProvider.notifier).turnOn();
      expect(
        c.read(notificationsProvider).value?.status,
        NotificationsStatus.blockedBySystem,
      );
      expect(push.topics, isEmpty);
      // The wish is remembered: a restart still shows the blocked state.
      expect(store.enabled, isTrue);
      final restarted = makeContainer();
      expect(await status(restarted), NotificationsStatus.blockedBySystem);
    });

    test('allowed later in the phone settings: on after returning', () async {
      push.answer = PushPermission.denied;
      final c = makeContainer();
      await status(c);
      await c.read(notificationsProvider.notifier).turnOn();
      expect(await status(c), NotificationsStatus.blockedBySystem);

      // Coming back without a change rebuilds nothing.
      resumes.add(null);
      await settle();
      expect(await status(c), NotificationsStatus.blockedBySystem);
      expect(push.calls, isEmpty);

      push.current = PushPermission.granted;
      resumes.add(null);
      await settle();
      expect(await status(c), NotificationsStatus.on);
      await settle();
      expect(push.topics, {'chain-bim', 'chain-sok'});
      expect(store.subscribed, {'bim', 'sok'});
      expect(push.autoInit, isTrue);
      expect(push.permissionRequests, 1);
    });

    test('turnOff from blocked: off, and returning changes nothing', () async {
      push.answer = PushPermission.denied;
      final c = makeContainer();
      await status(c);
      await c.read(notificationsProvider.notifier).turnOn();
      await c.read(notificationsProvider.notifier).turnOff();
      expect(await status(c), NotificationsStatus.off);
      push.current = PushPermission.granted;
      resumes.add(null);
      await settle();
      expect(await status(c), NotificationsStatus.off);
      expect(push.topics, isEmpty);
    });

    test(
      'a failing store keeps the previous state and does not throw',
      () async {
        final c = ProviderContainer.test(
          overrides: [
            pushMessagingProvider.overrideWith((ref) async => push),
            notificationsStoreProvider.overrideWithValue(_FailingStore()),
            favoritesStoreProvider.overrideWithValue(favorites),
            appResumedProvider.overrideWithValue(resumes.stream),
          ],
        );
        c.listen(notificationsProvider, (_, _) {});
        expect(await status(c), NotificationsStatus.off);
        await c.read(notificationsProvider.notifier).turnOn();
        expect(
          c.read(notificationsProvider).value?.status,
          NotificationsStatus.off,
        );
        expect(push.topics, isEmpty);
      },
    );
  });

  group('while on', () {
    setUp(() => store = MemoryNotificationsStore(enabled: true));

    test('favourites added and removed follow the topics', () async {
      push.current = PushPermission.granted;
      final c = makeContainer();
      expect(await status(c), NotificationsStatus.on);
      await settle();
      expect(push.topics, {'chain-bim', 'chain-sok'});

      await c.read(favoritesProvider.notifier).toggle('migros');
      await settle();
      expect(push.topics, {'chain-bim', 'chain-sok', 'chain-migros'});

      await c.read(favoritesProvider.notifier).toggle('bim');
      await settle();
      expect(push.topics, {'chain-sok', 'chain-migros'});
      expect(store.subscribed, {'sok', 'migros'});
      expect(push.permissionRequests, 0);
    });

    test(
      'a start with a stale record subscribes and unsubscribes the difference',
      () async {
        push.current = PushPermission.granted;
        store = MemoryNotificationsStore(
          enabled: true,
          subscribed: {'a101', 'bim'},
        );
        push.topics.addAll({'chain-a101', 'chain-bim'});
        final c = makeContainer();
        expect(await status(c), NotificationsStatus.on);
        await settle();
        expect(push.topics, {'chain-bim', 'chain-sok'});
        expect(push.calls, ['+chain-sok', '-chain-a101']);
        expect(store.subscribed, {'bim', 'sok'});
      },
    );

    test('a failed subscription is retried on the next sync', () async {
      push.current = PushPermission.granted;
      push.failing.add('chain-sok');
      final c = makeContainer();
      await status(c);
      await settle();
      expect(store.subscribed, {'bim'});

      push.failing.clear();
      await c.read(favoritesProvider.notifier).toggle('migros');
      await settle();
      expect(store.subscribed, {'bim', 'sok', 'migros'});
      expect(push.topics, {'chain-bim', 'chain-sok', 'chain-migros'});
    });

    test(
      'permission revoked in the system settings -> blockedBySystem',
      () async {
        push.current = PushPermission.denied;
        final c = makeContainer();
        expect(await status(c), NotificationsStatus.blockedBySystem);
        await settle();
        expect(push.calls, isEmpty);
      },
    );

    test(
      'turnOff unsubscribes everything and stops following favourites',
      () async {
        push.current = PushPermission.granted;
        final c = makeContainer();
        await status(c);
        await settle();
        await c.read(notificationsProvider.notifier).turnOff();
        expect(await status(c), NotificationsStatus.off);
        expect(push.topics, isEmpty);
        expect(store.enabled, isFalse);
        expect(store.subscribed, isEmpty);
        expect(push.autoInit, isFalse);

        await c.read(favoritesProvider.notifier).toggle('migros');
        await settle();
        expect(push.topics, isEmpty);
      },
    );

    test('turnOff -> turnOn subscribes again', () async {
      push.current = PushPermission.granted;
      final c = makeContainer();
      await status(c);
      await c.read(notificationsProvider.notifier).turnOff();
      await c.read(notificationsProvider.notifier).turnOn();
      expect(await status(c), NotificationsStatus.on);
      expect(push.topics, {'chain-bim', 'chain-sok'});
      expect(store.enabled, isTrue);
    });
  });

  test('off with leftovers of a failed turnOff cleans them up', () async {
    store = MemoryNotificationsStore(subscribed: {'bim'});
    push.topics.add('chain-bim');
    final c = makeContainer();
    expect(await status(c), NotificationsStatus.off);
    await settle();
    expect(push.topics, isEmpty);
    expect(store.subscribed, isEmpty);
  });

  group('taps', () {
    Matcher tapTo(String chainId, [String? brochureId]) =>
        isA<NotificationTap>()
            .having((t) => t.chainId, 'chainId', chainId)
            .having((t) => t.brochureId, 'brochureId', brochureId);

    test('NotificationTap.fromData', () {
      expect(
        NotificationTap.fromData({'chain_id': 'bim', 'brochure_id': 'b-1'}),
        tapTo('bim', 'b-1'),
      );
      expect(
        NotificationTap.fromData({'chain_id': 'bim', 'brochure_id': ''}),
        tapTo('bim'),
      );
      expect(NotificationTap.fromData({'brochure_id': 'b-1'}), isNull);
      expect(NotificationTap.fromData({'chain_id': 7}), isNull);
    });

    test('every tap is a distinct event, even on the same notification', () {
      final a = NotificationTap(chainId: 'bim', brochureId: 'b-1');
      final b = NotificationTap(chainId: 'bim', brochureId: 'b-1');
      expect(a == b, isFalse);
      expect(b.sequence, greaterThan(a.sequence));
      expect(a.sameTarget(b), isTrue);
    });

    test('the launch notification comes first, then background taps', () async {
      push.initial = NotificationTap(chainId: 'bim', brochureId: 'b-1');
      final c = makeContainer();
      final seen = <NotificationTap>[];
      c.listen<AsyncValue<NotificationTap>>(notificationTapProvider, (_, next) {
        if (next case AsyncData(:final value)) seen.add(value);
      });
      await settle();
      push.tapController.add(NotificationTap(chainId: 'sok'));
      await settle();
      expect(seen, [tapTo('bim', 'b-1'), tapTo('sok')]);
    });

    test(
      'tapping the same notification twice reaches listeners twice',
      () async {
        final c = makeContainer();
        final seen = <NotificationTap>[];
        c.listen<AsyncValue<NotificationTap>>(notificationTapProvider, (
          _,
          next,
        ) {
          if (next case AsyncData(:final value)) seen.add(value);
        });
        await settle();
        final data = {'chain_id': 'bim', 'brochure_id': 'b-1'};
        push.tapController.add(NotificationTap.fromData(data)!);
        await settle();
        push.tapController.add(NotificationTap.fromData(data)!);
        await settle();
        expect(seen, [tapTo('bim', 'b-1'), tapTo('bim', 'b-1')]);
      },
    );

    test('unavailable: never emits', () async {
      final c = makeContainer(available: false);
      final seen = <AsyncValue<NotificationTap>>[];
      c.listen<AsyncValue<NotificationTap>>(
        notificationTapProvider,
        (_, next) => seen.add(next),
      );
      await settle();
      expect(seen.whereType<AsyncData<NotificationTap>>(), isEmpty);
      expect(seen.whereType<AsyncError<NotificationTap>>(), isEmpty);
    });
  });

  test('permission revoked while away: blocked after returning', () async {
    store = MemoryNotificationsStore(enabled: true);
    push.current = PushPermission.granted;
    final c = makeContainer();
    expect(await status(c), NotificationsStatus.on);
    push.current = PushPermission.denied;
    resumes.add(null);
    await settle();
    expect(await status(c), NotificationsStatus.blockedBySystem);
  });

  group('openSystemSettings', () {
    test('returns what the opener says', () async {
      final c = makeContainer();
      final controller = c.read(notificationsProvider.notifier);
      expect(await controller.openSystemSettings(), isTrue);
      opener.result = false;
      expect(await controller.openSystemSettings(), isFalse);
      opener.error = Exception('no activity');
      expect(await controller.openSystemSettings(), isFalse);
      expect(opener.calls, 3);
    });

    test('Android asks MainActivity over the method channel', () async {
      TestWidgetsFlutterBinding.ensureInitialized();
      final messenger =
          TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
      final methods = <String>[];
      messenger.setMockMethodCallHandler(PlatformSystemSettingsOpener.channel, (
        call,
      ) async {
        methods.add(call.method);
        return true;
      });
      addTearDown(
        () => messenger.setMockMethodCallHandler(
          PlatformSystemSettingsOpener.channel,
          null,
        ),
      );
      final android = PlatformSystemSettingsOpener(
        platform: TargetPlatform.android,
      );
      expect(await android.openNotificationSettings(), isTrue);
      expect(methods, ['openNotificationSettings']);

      // No handler (e.g. an old build): false, not an exception.
      messenger.setMockMethodCallHandler(
        PlatformSystemSettingsOpener.channel,
        null,
      );
      expect(await android.openNotificationSettings(), isFalse);
    });

    test('iOS opens app-settings:, other platforms are unsupported', () async {
      final launched = <Uri>[];
      final ios = PlatformSystemSettingsOpener(
        platform: TargetPlatform.iOS,
        launch: (uri) async {
          launched.add(uri);
          return true;
        },
      );
      expect(await ios.openNotificationSettings(), isTrue);
      expect(launched, [Uri.parse('app-settings:')]);
      final failing = PlatformSystemSettingsOpener(
        platform: TargetPlatform.iOS,
        launch: (uri) => Future.error(Exception('cannot')),
      );
      expect(await failing.openNotificationSettings(), isFalse);
      final linux = PlatformSystemSettingsOpener(
        platform: TargetPlatform.linux,
      );
      expect(await linux.openNotificationSettings(), isFalse);
    });
  });

  test('PrefsNotificationsStore round trip', () async {
    SharedPreferences.setMockInitialValues({});
    final prefs = PrefsNotificationsStore();
    expect(await prefs.readEnabled(), isFalse);
    expect(await prefs.readSubscribed(), isEmpty);
    await prefs.writeEnabled(true);
    await prefs.writeSubscribed({'sok', 'bim'});
    expect(await prefs.readEnabled(), isTrue);
    expect(await prefs.readSubscribed(), {'bim', 'sok'});
  });

  test('topic names match the scraper', () {
    expect(notificationTopicForChain('bim'), 'chain-bim');
    expect(newBrochuresChannelId, 'new_brochures');
  });
}

class _FailingStore implements NotificationsStore {
  @override
  Future<bool> readEnabled() async => false;

  @override
  Future<Set<String>> readSubscribed() async => const {};

  @override
  Future<void> writeEnabled(bool enabled) => Future.error(Exception('disk'));

  @override
  Future<void> writeSubscribed(Set<String> chainIds) async {}
}

class FakeSettingsOpener implements SystemSettingsOpener {
  bool result = true;
  Object? error;
  int calls = 0;

  @override
  Future<bool> openNotificationSettings() async {
    calls++;
    if (error != null) throw error!;
    return result;
  }
}
