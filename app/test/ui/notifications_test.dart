// D4: "Yeni broşür bildirimi". The home screen control in each state, the
// offer window (after the first star, at most once), the way a tapped
// notification opens a brochure or a market, and the layout matrix.

import 'dart:async';

import 'package:aktuel_brosur/data/data.dart';
import 'package:aktuel_brosur/design/widgets/app_buttons.dart';
import 'package:aktuel_brosur/features/brochure/brochure_screen.dart';
import 'package:aktuel_brosur/features/chain/chain_screen.dart';
import 'package:aktuel_brosur/features/home/home_screen.dart';
import 'package:aktuel_brosur/features/notifications/notification_offer.dart';
import 'package:aktuel_brosur/features/notifications/notification_offer_store.dart';
import 'package:aktuel_brosur/features/notifications/notification_tap_handler.dart';
import 'package:aktuel_brosur/l10n/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support.dart';

const _off = ValueKey('notify-off');
const _on = ValueKey('notify-on');
const _blocked = ValueKey('notify-blocked');
const _howTo = ValueKey('notify-how-to');
const _turnOff = ValueKey('notify-turn-off');
const _openSettings = ValueKey('notify-open-settings');
const _yes = ValueKey('notify-offer-yes');
const _no = ValueKey('notify-offer-no');
const _tall = Size(411, 3000);
const _small = Size(320, 640);

Future<NotificationsLog> _home(
  WidgetTester tester, {
  NotificationsStatus status = NotificationsStatus.off,
  NotificationsStatus afterTurnOn = NotificationsStatus.on,
  Set<String> favorites = const {'sok'},
  MemoryNotificationOfferStore? offerStore,
  Size size = _tall,
  double textScale = 1,
  Brightness brightness = Brightness.light,
  bool reduceMotion = false,
  Widget screen = const HomeScreen(),
  bool settingsOpen = true,
}) async {
  final log = NotificationsLog(settingsOpen: settingsOpen);
  await pumpUi(
    tester,
    screen,
    overrides: uiOverrides(
      favorites: favorites,
      notifications: status,
      afterTurnOn: afterTurnOn,
      notificationsLog: log,
      offerStore: offerStore,
    ),
    size: size,
    textScale: textScale,
    brightness: brightness,
    reduceMotion: reduceMotion,
  );
  return log;
}

Future<void> _starFirst(WidgetTester tester, String name) async {
  final star = find.bySemanticsLabel(l10nOf(tester).favoriteAdd(name));
  await tester.ensureVisible(star);
  await tester.pumpAndSettle();
  await tester.tap(star);
  await tester.pumpAndSettle();
}

void main() {
  group('home control', () {
    testWidgets('unavailable: nothing is added to the home screen', (
      tester,
    ) async {
      await _home(tester, status: NotificationsStatus.unavailable);
      for (final key in [_off, _on, _blocked]) {
        expect(find.byKey(key), findsNothing);
      }
      expect(find.textContaining('bildirim'), findsNothing);
      expect(find.textContaining('Bildirim'), findsNothing);
    });

    testWidgets('no favourites: no control, whatever the status', (
      tester,
    ) async {
      await _home(tester, favorites: const {});
      expect(find.byKey(_off), findsNothing);
    });

    testWidgets('off: one button under the favourites opens the offer', (
      tester,
    ) async {
      final log = await _home(tester, favorites: const {'sok', 'bim'});
      final l10n = l10nOf(tester);

      expect(find.byKey(_off), findsOneWidget);
      expect(find.bySemanticsLabel(l10n.notifyOffSpoken), findsOneWidget);
      expect(tester.getSize(find.byKey(_off)).height, greaterThanOrEqualTo(64));
      // Under the favourites, above "Diğer marketler".
      expect(
        tester.getTopLeft(find.byKey(_off)).dy,
        lessThan(tester.getTopLeft(find.text(l10n.homeOthers)).dy),
      );

      await tester.tap(find.byKey(_off));
      await tester.pumpAndSettle();
      expect(find.text(l10n.notifyOfferTitle), findsOneWidget);
      // The one plain sentence names the markets, before the phone asks.
      expect(
        find.text(l10n.notifyOfferMessage(l10n.nameListTwo('BİM', 'Şok'))),
        findsOneWidget,
      );
      expect(find.text(l10n.notifyOfferPermissionNote), findsOneWidget);
      for (final key in [_yes, _no]) {
        expect(
          tester.getSize(find.byKey(key)).height,
          greaterThanOrEqualTo(56),
        );
      }

      await tester.tap(find.byKey(_yes));
      await tester.pumpAndSettle();
      expect(log.turnOnCalls, 1);
      expect(find.text(l10n.notifyTurnedOn), findsOneWidget);
      expect(find.byKey(_on), findsOneWidget);
      expect(find.byKey(_off), findsNothing);
    });

    testWidgets('off: "Şimdi değil" and the back button change nothing', (
      tester,
    ) async {
      final store = MemoryNotificationOfferStore();
      final log = await _home(tester, offerStore: store);

      await tester.tap(find.byKey(_off));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(_no));
      await tester.pumpAndSettle();
      expect(find.byKey(_no), findsNothing);

      await tester.tap(find.byKey(_off));
      await tester.pumpAndSettle();
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      expect(find.byKey(_no), findsNothing);

      expect(log.turnOnCalls, 0);
      expect(find.byKey(_off), findsOneWidget);
      expect(store.offered, isTrue);
    });

    testWidgets('off: a tap beside the window does not answer it', (
      tester,
    ) async {
      final log = await _home(tester);
      await tester.tap(find.byKey(_off));
      await tester.pumpAndSettle();
      await tester.tapAt(const Offset(4, 4));
      await tester.pumpAndSettle();
      expect(find.byKey(_yes), findsOneWidget);
      expect(log.turnOnCalls, 0);
    });

    testWidgets('the phone refuses: plain message, then the blocked panel', (
      tester,
    ) async {
      await _home(tester, afterTurnOn: NotificationsStatus.blockedBySystem);
      final l10n = l10nOf(tester);
      await tester.tap(find.byKey(_off));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(_yes));
      await tester.pumpAndSettle();
      expect(find.text(l10n.notifyNotAllowed), findsOneWidget);
      expect(find.byKey(_blocked), findsOneWidget);
    });

    testWidgets('on: says so, for which markets, and how to turn it off', (
      tester,
    ) async {
      final log = await _home(
        tester,
        status: NotificationsStatus.on,
        favorites: const {'sok', 'bim', 'migros'},
      );
      final l10n = l10nOf(tester);

      expect(find.text(l10n.notifyOnTitle), findsOneWidget);
      expect(
        find.text(
          l10n.notifyOnDetail(l10n.nameListThree('BİM', 'Şok', 'Migros')),
        ),
        findsOneWidget,
      );
      final turnOff = find.byKey(_turnOff);
      expect(tester.getSize(turnOff).height, greaterThanOrEqualTo(56));
      expect(
        find.descendant(of: turnOff, matching: find.text(l10n.notifyTurnOff)),
        findsOneWidget,
      );

      await tester.tap(turnOff);
      await tester.pumpAndSettle();
      expect(log.turnOffCalls, 1);
      expect(find.text(l10n.notifyTurnedOff), findsOneWidget);
      expect(find.byKey(_off), findsOneWidget);
    });

    testWidgets('on with many favourites counts them instead of listing', (
      tester,
    ) async {
      await _home(
        tester,
        status: NotificationsStatus.on,
        favorites: const {'sok', 'bim', 'migros', 'watsons'},
      );
      final l10n = l10nOf(tester);
      expect(
        find.text(l10n.notifyOnDetail(l10n.favoriteChainsCount(4))),
        findsOneWidget,
      );
    });

    testWidgets('blocked: a big button opens the phone settings', (
      tester,
    ) async {
      final log = await _home(
        tester,
        status: NotificationsStatus.blockedBySystem,
      );
      final l10n = l10nOf(tester);

      final open = find.byKey(_openSettings);
      expect(
        find.descendant(of: open, matching: find.text(l10n.notifyOpenSettings)),
        findsOneWidget,
      );
      expect(tester.getSize(open).height, greaterThanOrEqualTo(64));
      // Above the quieter "by hand" button.
      expect(
        tester.getTopLeft(open).dy,
        lessThan(tester.getTopLeft(find.byKey(_howTo)).dy),
      );

      await tester.tap(open);
      await tester.pumpAndSettle();
      expect(log.settingsCalls, 1);
      // Opened: no message, the steps stay folded.
      expect(find.text(l10n.notifySettingsFailed), findsNothing);
      expect(find.text(l10n.notifyBlockedStep1), findsNothing);
    });

    testWidgets('blocked: settings cannot open, so the steps show', (
      tester,
    ) async {
      final log = await _home(
        tester,
        status: NotificationsStatus.blockedBySystem,
        settingsOpen: false,
      );
      final l10n = l10nOf(tester);
      await tester.tap(find.byKey(_openSettings));
      await tester.pumpAndSettle();
      expect(log.settingsCalls, 1);
      expect(find.text(l10n.notifySettingsFailed), findsOneWidget);
      expect(find.text(l10n.notifyBlockedStep1), findsOneWidget);
      expect(find.text(l10n.notifyBlockedHideSteps), findsOneWidget);

      // Pressing again keeps them open.
      await tester.tap(find.byKey(_openSettings));
      await tester.pumpAndSettle();
      expect(find.text(l10n.notifyBlockedStep1), findsOneWidget);
    });

    testWidgets('blocked: explains, written steps one button away', (
      tester,
    ) async {
      await _home(tester, status: NotificationsStatus.blockedBySystem);
      final l10n = l10nOf(tester);

      expect(find.text(l10n.notifyBlockedTitle), findsOneWidget);
      expect(find.text(l10n.notifyBlockedDetail), findsOneWidget);
      expect(find.text(l10n.notifyBlockedHowTo), findsOneWidget);
      expect(find.text(l10n.notifyBlockedStep1), findsNothing);
      expect(
        tester.getSize(find.byKey(_howTo)).height,
        greaterThanOrEqualTo(56),
      );

      await tester.tap(find.byKey(_howTo));
      await tester.pumpAndSettle();
      expect(find.text(l10n.notifyBlockedStep1), findsOneWidget);
      expect(find.text(l10n.notifyBlockedStep2(l10n.appTitle)), findsOneWidget);
      expect(find.text(l10n.notifyBlockedStep3), findsOneWidget);
      expect(
        find.bySemanticsLabel(
          l10n.notifyStepSpoken(1, l10n.notifyBlockedStep1),
        ),
        findsOneWidget,
      );
      expect(find.text(l10n.notifyBlockedHideSteps), findsOneWidget);

      await tester.tap(find.byKey(_howTo));
      await tester.pumpAndSettle();
      expect(find.text(l10n.notifyBlockedStep1), findsNothing);
    });

    testWidgets('with reduced motion the window appears at once', (
      tester,
    ) async {
      await _home(tester, reduceMotion: true);
      await tester.tap(find.byKey(_off));
      await tester.pump();
      await tester.pump();
      expect(find.byKey(_yes), findsOneWidget);
      final route = ModalRoute.of(tester.element(find.byKey(_yes)))!;
      expect(route.animation!.value, 1);
    });

    testWidgets('with motion the window fades in briefly', (tester) async {
      await _home(tester);
      await tester.tap(find.byKey(_off));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 60));
      final route = ModalRoute.of(tester.element(find.byKey(_yes)))!;
      expect(route.animation!.value, inExclusiveRange(0, 1));
      await tester.pumpAndSettle();
    });
  });

  group('offer after the first star', () {
    testWidgets('shown once: with the star message, never again on its own', (
      tester,
    ) async {
      final store = MemoryNotificationOfferStore();
      final log = await _home(tester, favorites: const {}, offerStore: store);
      final l10n = l10nOf(tester);

      await _starFirst(tester, 'Şok');
      // The window also says where the card went (its snack is skipped).
      expect(find.text(l10n.favoriteAdded('Şok')), findsOneWidget);
      expect(find.text(l10n.notifyOfferTitle), findsOneWidget);
      expect(find.text(l10n.notifyOfferMessage('Şok')), findsOneWidget);
      expect(store.offered, isTrue);

      await tester.tap(find.byKey(_no));
      await tester.pumpAndSettle();
      expect(log.turnOnCalls, 0);

      // Un-star and star again, then a second market: no window.
      await tester.tap(find.bySemanticsLabel(l10n.favoriteRemove('Şok')));
      await tester.pumpAndSettle();
      await _starFirst(tester, 'BİM');
      expect(find.text(l10n.notifyOfferTitle), findsNothing);
      expect(find.text(l10n.favoriteAdded('BİM')), findsOneWidget);
      await _starFirst(tester, 'Şok');
      expect(find.text(l10n.notifyOfferTitle), findsNothing);
    });

    testWidgets('yes switches notifications on', (tester) async {
      final log = await _home(tester, favorites: const {});
      await _starFirst(tester, 'Şok');
      await tester.tap(find.byKey(_yes));
      await tester.pumpAndSettle();
      expect(log.turnOnCalls, 1);
      expect(find.text(l10nOf(tester).notifyTurnedOn), findsOneWidget);
      expect(find.byKey(_on), findsOneWidget);
    });

    testWidgets('not after a second star (the first came before)', (
      tester,
    ) async {
      await _home(tester, favorites: const {'bim'});
      await _starFirst(tester, 'Şok');
      expect(find.text(l10nOf(tester).notifyOfferTitle), findsNothing);
    });

    testWidgets('not when it was already made', (tester) async {
      await _home(
        tester,
        favorites: const {},
        offerStore: MemoryNotificationOfferStore(offered: true),
      );
      await _starFirst(tester, 'Şok');
      expect(find.text(l10nOf(tester).notifyOfferTitle), findsNothing);
    });

    for (final status in [
      NotificationsStatus.unavailable,
      NotificationsStatus.on,
      NotificationsStatus.blockedBySystem,
    ]) {
      testWidgets('not when notifications are ${status.name}', (tester) async {
        final store = MemoryNotificationOfferStore();
        await _home(
          tester,
          status: status,
          favorites: const {},
          offerStore: store,
        );
        await _starFirst(tester, 'Şok');
        final l10n = l10nOf(tester);
        expect(find.text(l10n.notifyOfferTitle), findsNothing);
        expect(find.text(l10n.favoriteAdded('Şok')), findsOneWidget);
        // Still available for when notifications become possible.
        expect(store.offered, isFalse);
      });
    }

    testWidgets('the market screen star offers it too', (tester) async {
      await _home(
        tester,
        favorites: const {},
        screen: const ChainScreen(chainId: 'bim'),
      );
      await _starFirst(tester, 'BİM');
      expect(find.text(l10nOf(tester).notifyOfferTitle), findsOneWidget);
    });
  });

  group('tapping a notification', () {
    Future<StreamController<NotificationTap>> pumpWithTaps(
      WidgetTester tester,
    ) async {
      final taps = StreamController<NotificationTap>();
      addTearDown(taps.close);
      final image = await makeTestImage(tester);
      await pumpUi(
        tester,
        const NotificationTapHandler(child: HomeScreen()),
        overrides: uiOverrides(image: image, taps: taps.stream),
      );
      return taps;
    }

    Future<void> send(
      WidgetTester tester,
      StreamController<NotificationTap> taps,
      NotificationTap tap,
    ) async {
      taps.add(tap);
      await tester.pumpAndSettle();
    }

    testWidgets('opens the named brochure directly', (tester) async {
      final taps = await pumpWithTaps(tester);
      await send(
        tester,
        taps,
        fakeTap(
          chainId: 'sok',
          brochureId: 'sok-2026-11-18-haftanin-firsatlari',
        ),
      );
      final screen = tester.widget<BrochureScreen>(find.byType(BrochureScreen));
      expect(screen.brochureId, 'sok-2026-11-18-haftanin-firsatlari');
      expect(find.byType(ChainScreen), findsNothing);

      // "Geri" returns to where the user was: no market screen in between.
      await tester.tap(find.text(l10nOf(tester).back));
      await tester.pumpAndSettle();
      expect(find.byType(HomeScreen), findsOneWidget);
      expect(find.byType(ChainScreen), findsNothing);
    });

    testWidgets('a brochure no longer in the catalog opens the market', (
      tester,
    ) async {
      final taps = await pumpWithTaps(tester);
      await send(tester, taps, fakeTap(chainId: 'bim', brochureId: 'gone'));
      expect(find.byType(ChainScreen), findsOneWidget);
      expect(find.byType(BrochureScreen), findsNothing);
    });

    testWidgets('no brochure named: the market, as its card would open it', (
      tester,
    ) async {
      final taps = await pumpWithTaps(tester);
      await send(tester, taps, fakeTap(chainId: 'bim'));
      expect(find.byType(ChainScreen), findsOneWidget);
    });

    testWidgets('a brochure of another market is not trusted', (tester) async {
      final taps = await pumpWithTaps(tester);
      await send(
        tester,
        taps,
        fakeTap(chainId: 'bim', brochureId: 'migros-910'),
      );
      expect(find.byType(ChainScreen), findsOneWidget);
      expect(find.byType(BrochureScreen), findsNothing);
    });

    testWidgets('a second tap on the same notification opens it again', (
      tester,
    ) async {
      final taps = await pumpWithTaps(tester);
      await send(tester, taps, fakeTap(chainId: 'bim'));
      expect(find.byType(ChainScreen), findsOneWidget);
      await tester.tap(find.text(l10nOf(tester).back));
      await tester.pumpAndSettle();
      expect(find.byType(ChainScreen), findsNothing);
      await send(tester, taps, fakeTap(chainId: 'bim'));
      expect(find.byType(ChainScreen), findsOneWidget);
    });

    testWidgets('a tap for another market after coming back', (tester) async {
      final taps = await pumpWithTaps(tester);
      await send(tester, taps, fakeTap(chainId: 'bim'));
      await tester.tap(find.text(l10nOf(tester).back));
      await tester.pumpAndSettle();
      await send(tester, taps, fakeTap(chainId: 'sok'));
      expect(find.byType(ChainScreen), findsOneWidget);
    });

    testWidgets('an unknown market leaves the user at home', (tester) async {
      final taps = await pumpWithTaps(tester);
      await send(tester, taps, fakeTap(chainId: 'nowhere', brochureId: 'x'));
      expect(find.byType(ChainScreen), findsNothing);
      expect(find.byType(BrochureScreen), findsNothing);
      expect(find.byType(HomeScreen), findsOneWidget);
    });
  });

  test('names read as a sentence', () {
    final l10n = lookupAppLocalizations(const Locale('tr'));
    expect(chainNamesPhrase(l10n, ['Şok']), 'Şok');
    expect(chainNamesPhrase(l10n, ['Şok', 'BİM']), 'Şok ve BİM');
    expect(
      chainNamesPhrase(l10n, ['Şok', 'BİM', 'Migros']),
      'Şok, BİM ve Migros',
    );
    expect(
      chainNamesPhrase(l10n, ['Şok', 'BİM', 'Migros', 'A101']),
      'Sık baktığınız 4 market',
    );
  });

  group('no overflow', () {
    for (final size in [phoneSize, _small]) {
      for (final scale in [1.0, 1.3, 2.0]) {
        for (final brightness in Brightness.values) {
          final where =
              '${size.width.toInt()} dp, scale $scale, ${brightness.name}';
          for (final status in [
            NotificationsStatus.off,
            NotificationsStatus.on,
            NotificationsStatus.blockedBySystem,
          ]) {
            testWidgets('${status.name} control at $where', (tester) async {
              await _home(
                tester,
                status: status,
                favorites: const {'sok', 'bim', 'migros'},
                size: size,
                textScale: scale,
                brightness: brightness,
              );
              if (status == NotificationsStatus.blockedBySystem) {
                await tester.ensureVisible(find.byKey(_howTo));
                await tester.pumpAndSettle();
                await tester.tap(find.byKey(_howTo));
                await tester.pumpAndSettle();
              }
              expect(tester.takeException(), isNull);
              await tester.drag(find.byType(ListView), const Offset(0, -4000));
              await tester.pumpAndSettle();
              expect(tester.takeException(), isNull);
            });
          }
          testWidgets('offer window at $where', (tester) async {
            await _home(
              tester,
              favorites: const {},
              size: size,
              textScale: scale,
              brightness: brightness,
            );
            await tester.ensureVisible(
              find.bySemanticsLabel(l10nOf(tester).favoriteAdd('Şok')),
            );
            await tester.pumpAndSettle();
            await _starFirst(tester, 'Şok');
            expect(tester.takeException(), isNull);
            // Everything reachable: the window scrolls when it is too tall.
            await tester.ensureVisible(find.byKey(_no));
            await tester.pumpAndSettle();
            expect(tester.takeException(), isNull);
            expect(
              tester.getSize(find.byKey(_no)).height,
              greaterThanOrEqualTo(56),
            );
            await tester.tap(find.byKey(_no));
            await tester.pumpAndSettle();
          });
        }
      }
    }
  });

  testWidgets('the control uses only app buttons (56 dp and up)', (
    tester,
  ) async {
    await _home(tester, status: NotificationsStatus.on);
    for (final button in tester.widgetList(find.byType(AppButton))) {
      expect(
        tester.getSize(find.byWidget(button)).height,
        greaterThanOrEqualTo(56),
      );
    }
  });
}
