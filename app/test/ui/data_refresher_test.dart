import 'dart:async';

import 'package:aktuel_brosur/data/data.dart';
import 'package:aktuel_brosur/design/widgets/feedback.dart';
import 'package:aktuel_brosur/features/app/app.dart';
import 'package:aktuel_brosur/features/home/chain_card.dart';
import 'package:aktuel_brosur/features/home/home_screen.dart';
import 'package:aktuel_brosur/l10n/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support.dart';

/// A clock the test moves by hand.
class _TestClock extends Clock {
  _TestClock(this._now);

  final DateTime Function() _now;

  @override
  DateTime now() => _now();
}

void main() {
  late DateTime now;
  late FakeRepository repository;

  Future<void> pumpApp(WidgetTester tester) async {
    tester.view.physicalSize = phoneSize;
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(
      ProviderScope(
        overrides: uiOverrides(
          repository: repository,
          // A new instance per build, like the real clock provider.
          clock: clockProvider.overrideWith((ref) => _TestClock(() => now)),
        ),
        child: const CarsiPazarApp(showSplash: false),
      ),
    );
    await tester.pump();
    await tester.pump();
  }

  // The app goes to the background and comes back, through the states the
  // platform reports.
  Future<void> leaveAndReturn(WidgetTester tester) async {
    for (final state in const [
      AppLifecycleState.inactive,
      AppLifecycleState.hidden,
      AppLifecycleState.paused,
      AppLifecycleState.hidden,
      AppLifecycleState.inactive,
      AppLifecycleState.resumed,
    ]) {
      tester.binding.handleAppLifecycleStateChanged(state);
    }
    await tester.pump();
    await tester.pump();
  }

  ProviderContainer containerOf(WidgetTester tester) =>
      ProviderScope.containerOf(tester.element(find.byType(HomeScreen)));

  testWidgets('returning on the next day updates "Bugün" and the groups', (
    tester,
  ) async {
    now = DateTime(2026, 11, 13, 21);
    repository = FakeRepository(
      fetchedAt: now.subtract(const Duration(minutes: 5)).toUtc(),
    );
    await pumpApp(tester);
    expect(find.text('Bugün 13 Kasım Cuma'), findsOneWidget);
    final before = containerOf(tester).read(chainSummaryProvider('bim')).value!;
    expect(before.currentCount, 1);

    // The phone sat in a pocket overnight; nothing changes until it is
    // opened again.
    now = DateTime(2026, 11, 14, 8, 15);
    await tester.pump();
    expect(find.text('Bugün 13 Kasım Cuma'), findsOneWidget);

    await leaveAndReturn(tester);
    expect(find.text('Bugün 14 Kasım Cumartesi'), findsOneWidget);
    expect(find.text('Bugün 13 Kasım Cuma'), findsNothing);
    // Friday's single-day BİM flyer moved from "Bu hafta" to "Geçmiş".
    final after = containerOf(tester).read(chainSummaryProvider('bim')).value!;
    expect(after.currentCount, 0);
    expect(after.pastCount, before.pastCount + 1);
    expect(tester.takeException(), isNull);
  });

  testWidgets('left open across midnight, the day turns at midnight', (
    tester,
  ) async {
    now = DateTime(2026, 11, 13, 23, 59, 30);
    repository = FakeRepository(fetchedAt: now.toUtc());
    await pumpApp(tester);
    expect(find.text('Bugün 13 Kasım Cuma'), findsOneWidget);

    now = DateTime(2026, 11, 14, 0, 0, 1);
    await tester.pump(const Duration(seconds: 31));
    await tester.pump();
    expect(find.text('Bugün 14 Kasım Cumartesi'), findsOneWidget);
    // Only the day changes at midnight; the catalog is not downloaded.
    expect(repository.loadCount, 1);
  });

  group('back in the foreground on the same day', () {
    testWidgets('a catalog fetched 29 minutes ago is kept', (tester) async {
      now = DateTime(2026, 11, 13, 10);
      repository = FakeRepository(
        fetchedAt: now.subtract(const Duration(minutes: 29)).toUtc(),
      );
      await pumpApp(tester);
      expect(repository.loadCount, 1);

      await leaveAndReturn(tester);
      expect(repository.loadCount, 1);
      expect(find.text('Bugün 13 Kasım Cuma'), findsOneWidget);
    });

    testWidgets('a catalog fetched 31 minutes ago is fetched again', (
      tester,
    ) async {
      now = DateTime(2026, 11, 13, 10);
      repository = FakeRepository(
        fetchedAt: now.subtract(const Duration(minutes: 31)).toUtc(),
      );
      await pumpApp(tester);
      expect(repository.loadCount, 1);

      await leaveAndReturn(tester);
      expect(repository.loadCount, 2);
      expect(find.byType(ChainCard), findsWidgets);
    });

    testWidgets('a failed quiet refresh leaves the screen as it was', (
      tester,
    ) async {
      now = DateTime(2026, 11, 13, 10);
      repository = FakeRepository(
        fetchedAt: now.subtract(const Duration(hours: 3)).toUtc(),
      );
      await pumpApp(tester);
      final cards = find.byType(ChainCard).evaluate().length;
      expect(cards, greaterThan(0));

      repository.error = const CatalogUnavailableException('offline');
      await leaveAndReturn(tester);
      expect(repository.loadCount, 2);
      // Same cards, no error view, no message.
      expect(find.byType(ChainCard), findsNWidgets(cards));
      expect(find.byType(StateView), findsNothing);
      expect(find.byType(SnackBar), findsNothing);
      expect(tester.takeException(), isNull);
    });
  });

  group('offline with a saved catalog', () {
    Finder offlineBanner(WidgetTester tester) => find.widgetWithText(
      NoticeStrip,
      AppLocalizations.of(tester.element(find.byType(HomeScreen))).staleNotice,
    );

    // The emulator report: opened online, then cold-started in airplane
    // mode a few minutes later, so the saved copy is "fresh" by age.
    FakeRepository offlineRepository() => FakeRepository(
      isStale: true,
      fetchedAt: now.subtract(const Duration(minutes: 5)).toUtc(),
    );

    void goToBackground(WidgetTester tester) {
      for (final state in const [
        AppLifecycleState.inactive,
        AppLifecycleState.hidden,
        AppLifecycleState.paused,
      ]) {
        tester.binding.handleAppLifecycleStateChanged(state);
      }
    }

    Future<void> comeBack(WidgetTester tester) async {
      for (final state in const [
        AppLifecycleState.hidden,
        AppLifecycleState.inactive,
        AppLifecycleState.resumed,
      ]) {
        tester.binding.handleAppLifecycleStateChanged(state);
      }
      await tester.pump();
      await tester.pump();
    }

    setUp(() => now = DateTime(2026, 11, 13, 10));

    testWidgets('coming back retries at once and the banner goes away', (
      tester,
    ) async {
      repository = offlineRepository();
      await pumpApp(tester);
      expect(offlineBanner(tester), findsOneWidget);
      expect(repository.loadCount, 1);

      // Airplane mode off; the saved copy is only five minutes old, yet the
      // banner claims there is no internet, so it must be checked again.
      repository.isStale = false;
      await leaveAndReturn(tester);
      expect(repository.loadCount, 2);
      expect(offlineBanner(tester), findsNothing);
      expect(find.byType(ChainCard), findsWidgets);
    });

    testWidgets('returning from a covering window (inactive) also retries', (
      tester,
    ) async {
      // Pulling down the quick settings to turn airplane mode off only makes
      // the app inactive, never hidden.
      repository = offlineRepository();
      await pumpApp(tester);
      repository.isStale = false;
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pump();
      await tester.pump();
      expect(repository.loadCount, 2);
      expect(offlineBanner(tester), findsNothing);
    });

    testWidgets('in the foreground it retries quietly every 30 seconds', (
      tester,
    ) async {
      repository = offlineRepository();
      await pumpApp(tester);
      expect(repository.loadCount, 1);

      await tester.pump(const Duration(seconds: 29));
      expect(repository.loadCount, 1);
      await tester.pump(const Duration(seconds: 1));
      await tester.pump();
      expect(repository.loadCount, 2);
      expect(offlineBanner(tester), findsOneWidget);

      await tester.pump(offlineRetryInterval);
      await tester.pump();
      expect(repository.loadCount, 3);

      // The network is back: the next quiet retry clears the banner.
      repository.isStale = false;
      await tester.pump(offlineRetryInterval);
      await tester.pump();
      expect(repository.loadCount, 4);
      expect(offlineBanner(tester), findsNothing);
      expect(find.byType(SnackBar), findsNothing);

      // Online again: no more retries.
      await tester.pump(const Duration(minutes: 10));
      expect(repository.loadCount, 4);
    });

    testWidgets('in the background nothing is retried', (tester) async {
      repository = offlineRepository();
      await pumpApp(tester);
      await tester.pump(const Duration(seconds: 20));

      goToBackground(tester);
      // Longer than the 30-minute rule, yet the clock is not consulted while
      // in the background; nothing downloads until the app is opened.
      await tester.pump(const Duration(hours: 1));
      expect(repository.loadCount, 1);

      repository.isStale = false;
      await comeBack(tester);
      expect(repository.loadCount, 2);
      expect(offlineBanner(tester), findsNothing);
    });

    testWidgets('a failed retry keeps the saved catalog and the banner', (
      tester,
    ) async {
      repository = offlineRepository();
      await pumpApp(tester);
      final cards = find.byType(ChainCard).evaluate().length;
      expect(cards, greaterThan(0));

      // Still offline: the repository serves the saved copy again.
      await tester.pump(offlineRetryInterval);
      await tester.pump();
      expect(repository.loadCount, 2);
      expect(offlineBanner(tester), findsOneWidget);
      expect(find.byType(ChainCard), findsNWidgets(cards));

      // A retry that throws keeps everything as it was too.
      repository.error = const CatalogUnavailableException('offline');
      await tester.pump(offlineRetryInterval);
      await tester.pump();
      expect(repository.loadCount, 3);
      expect(offlineBanner(tester), findsOneWidget);
      expect(find.byType(ChainCard), findsNWidgets(cards));
      expect(find.byType(StateView), findsNothing);
      expect(find.byType(SnackBar), findsNothing);

      // ... and the retries go on.
      repository
        ..error = null
        ..isStale = false;
      await tester.pump(offlineRetryInterval);
      await tester.pump();
      expect(repository.loadCount, 4);
      expect(offlineBanner(tester), findsNothing);
      expect(tester.takeException(), isNull);
    });

    testWidgets('while a retry runs the saved catalog stays, no spinner', (
      tester,
    ) async {
      final gated = _GatedRepository(
        fetchedAt: now.subtract(const Duration(minutes: 5)).toUtc(),
      )..isStale = true;
      repository = gated;
      await pumpApp(tester);
      final cards = find.byType(ChainCard).evaluate().length;

      gated.gate = Completer<void>();
      await tester.pump(offlineRetryInterval);
      await tester.pump();
      expect(repository.loadCount, 2);
      expect(offlineBanner(tester), findsOneWidget);
      expect(find.byType(ChainCard), findsNWidgets(cards));
      expect(find.byType(RefreshProgressIndicator), findsNothing);
      expect(find.byType(CircularProgressIndicator), findsNothing);

      gated.isStale = false;
      gated.gate!.complete();
      await tester.pump();
      await tester.pump();
      expect(offlineBanner(tester), findsNothing);
      expect(find.byType(ChainCard), findsNWidgets(cards));
    });

    testWidgets('a quiet refresh that finds no network starts the retries', (
      tester,
    ) async {
      repository = FakeRepository(
        fetchedAt: now.subtract(const Duration(minutes: 31)).toUtc(),
      );
      await pumpApp(tester);
      expect(offlineBanner(tester), findsNothing);

      repository.isStale = true;
      await leaveAndReturn(tester);
      expect(repository.loadCount, 2);
      expect(offlineBanner(tester), findsOneWidget);

      repository.isStale = false;
      await tester.pump(offlineRetryInterval);
      await tester.pump();
      expect(repository.loadCount, 3);
      expect(offlineBanner(tester), findsNothing);
    });

    testWidgets('online with a fresh catalog nothing extra is fetched', (
      tester,
    ) async {
      repository = FakeRepository(
        fetchedAt: now.subtract(const Duration(minutes: 5)).toUtc(),
      );
      await pumpApp(tester);
      await tester.pump(const Duration(minutes: 10));
      expect(repository.loadCount, 1);
      await leaveAndReturn(tester);
      expect(repository.loadCount, 1);
    });

    testWidgets('with nothing saved there are no timed retries', (
      tester,
    ) async {
      repository = FakeRepository(
        error: const CatalogUnavailableException('offline'),
      );
      await pumpApp(tester);
      expect(find.byType(StateView), findsOneWidget);
      await tester.pump(const Duration(minutes: 5));
      expect(repository.loadCount, 1);
      expect(find.byType(StateView), findsOneWidget);
    });
  });
}

/// Holds [loadCatalog] until [gate] completes, to look at the screen while a
/// download is running.
class _GatedRepository extends FakeRepository {
  _GatedRepository({super.fetchedAt});

  Completer<void>? gate;

  @override
  Future<CatalogResult> loadCatalog({bool forceRefresh = false}) async {
    final wait = gate;
    if (wait != null) {
      loadCount++;
      await wait.future;
      loadCount--;
    }
    return super.loadCatalog(forceRefresh: forceRefresh);
  }
}
