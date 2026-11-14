import 'package:aktuel_brosur/data/data.dart';
import 'package:aktuel_brosur/design/widgets/feedback.dart';
import 'package:aktuel_brosur/features/app/app.dart';
import 'package:aktuel_brosur/features/home/chain_card.dart';
import 'package:aktuel_brosur/features/home/home_screen.dart';
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
}
