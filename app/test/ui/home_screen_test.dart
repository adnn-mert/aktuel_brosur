import 'package:aktuel_brosur/data/data.dart';
import 'package:aktuel_brosur/design/widgets/app_buttons.dart';
import 'package:aktuel_brosur/design/widgets/feedback.dart';
import 'package:aktuel_brosur/features/app/navigation.dart';
import 'package:aktuel_brosur/features/brochure/brochure_screen.dart';
import 'package:aktuel_brosur/features/chain/chain_screen.dart';
import 'package:aktuel_brosur/features/home/chain_card.dart';
import 'package:aktuel_brosur/features/home/home_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers.dart';
import 'support.dart';

const _names = [
  'BİM',
  'A101',
  'Şok',
  'Migros',
  'Watsons',
  'CarrefourSA',
  'Gratis',
];

Finder _card(String chainId) => find.byKey(ValueKey('chain-$chainId'));

void main() {
  testWidgets('shows the question and every market as a card', (tester) async {
    await pumpUi(
      tester,
      const HomeScreen(),
      overrides: uiOverrides(),
      size: const Size(411, 3000),
    );
    final l10n = l10nOf(tester);

    expect(find.text(l10n.appTitle), findsOneWidget);
    expect(find.text(l10n.homeQuestion), findsOneWidget);
    expect(find.text('Bugün 13 Kasım Cuma'), findsOneWidget);
    expect(find.byType(ChainCard), findsNWidgets(_names.length));
    for (final name in _names) {
      expect(
        find.bySemanticsLabel(RegExp('^${RegExp.escape(name)}, ')),
        findsOneWidget,
        reason: name,
      );
    }
    // No favourites yet: no section headings, but the star is explained.
    expect(find.text(l10n.homeFavorites), findsNothing);
    expect(find.text(l10n.homeFavoriteHint), findsOneWidget);
    // BİM has a brochure first seen today; Watsons does not.
    expect(
      find.descendant(of: _card('bim'), matching: find.text(l10n.badgeNew)),
      findsOneWidget,
    );
    expect(
      find.descendant(of: _card('watsons'), matching: find.text(l10n.badgeNew)),
      findsNothing,
    );
    expect(
      find.descendant(of: _card('a101'), matching: find.text(l10n.cardWeb)),
      findsOneWidget,
    );
  });

  testWidgets('starring a market moves it to the top section', (tester) async {
    await pumpUi(
      tester,
      const HomeScreen(),
      overrides: uiOverrides(),
      size: const Size(411, 3000),
    );
    final l10n = l10nOf(tester);

    await tester.tap(find.bySemanticsLabel(l10n.favoriteAdd('Şok')));
    await tester.pump();
    await tester.pump();

    expect(find.text(l10n.homeFavorites), findsOneWidget);
    expect(find.text(l10n.homeOthers), findsOneWidget);
    expect(find.text(l10n.favoriteAdded('Şok')), findsOneWidget);
    expect(find.bySemanticsLabel(l10n.favoriteRemove('Şok')), findsOneWidget);
    // Şok is now above BİM.
    expect(
      tester.getTopLeft(_card('sok')).dy,
      lessThan(tester.getTopLeft(_card('bim')).dy),
    );
    final star = tester.widget<FavoriteStar>(
      find.descendant(of: _card('sok'), matching: find.byType(FavoriteStar)),
    );
    expect(star.isFavorite, isTrue);
  });

  testWidgets('saved favourites are on top when the app opens', (tester) async {
    await pumpUi(
      tester,
      const HomeScreen(),
      overrides: uiOverrides(favorites: {'gratis'}),
      size: const Size(411, 3000),
    );
    expect(
      tester.getTopLeft(_card('gratis')).dy,
      lessThan(tester.getTopLeft(_card('bim')).dy),
    );
  });

  testWidgets('every touch target on a card is at least 56 dp', (tester) async {
    await pumpUi(tester, const HomeScreen(), overrides: uiOverrides());
    for (final star in tester.widgetList(find.byType(FavoriteStar))) {
      final size = tester.getSize(find.byWidget(star));
      expect(size.width, greaterThanOrEqualTo(56));
      expect(size.height, greaterThanOrEqualTo(56));
    }
    final card = tester.getSize(_card('bim'));
    expect(card.height, greaterThanOrEqualTo(56));
  });

  for (final scale in [1.0, 1.3, 2.0]) {
    for (final brightness in Brightness.values) {
      testWidgets(
        'no overflow at font scale $scale, ${brightness.name} theme',
        (tester) async {
          await pumpUi(
            tester,
            const HomeScreen(),
            overrides: uiOverrides(favorites: {'sok'}),
            textScale: scale,
            brightness: brightness,
          );
          expect(tester.takeException(), isNull);
          // Scroll through the whole list; nothing may overflow anywhere.
          await tester.drag(find.byType(ListView), const Offset(0, -3000));
          await tester.pump();
          expect(tester.takeException(), isNull);
        },
      );
    }
  }

  testWidgets('first launch without internet: plain words and a big retry', (
    tester,
  ) async {
    final repository = FakeRepository(
      error: const CatalogUnavailableException('offline'),
    );
    await pumpUi(
      tester,
      const HomeScreen(),
      overrides: uiOverrides(repository: repository),
    );
    final l10n = l10nOf(tester);

    expect(find.text(l10n.offlineTitle), findsOneWidget);
    expect(find.text(l10n.offlineMessage), findsOneWidget);
    final retry = find.widgetWithText(AppButton, l10n.retry);
    expect(tester.getSize(retry).height, greaterThanOrEqualTo(56));

    repository.error = null;
    await tester.tap(retry);
    await tester.pump();
    await tester.pump();
    expect(find.byType(ChainCard), findsWidgets);
  });

  testWidgets('broken data is explained differently from no internet', (
    tester,
  ) async {
    await pumpUi(
      tester,
      const HomeScreen(),
      overrides: uiOverrides(
        repository: FakeRepository(error: const CatalogFormatException('bad')),
      ),
    );
    expect(find.text(l10nOf(tester).brokenTitle), findsOneWidget);
  });

  testWidgets('offline with saved data shows a calm notice, not an error', (
    tester,
  ) async {
    await pumpUi(
      tester,
      const HomeScreen(),
      overrides: uiOverrides(repository: FakeRepository(isStale: true)),
    );
    final l10n = l10nOf(tester);
    expect(find.widgetWithText(NoticeStrip, l10n.staleNotice), findsOneWidget);
    expect(find.byType(ChainCard), findsWidgets);
  });

  testWidgets('data that needs a newer app shows the update notice', (
    tester,
  ) async {
    final json = sampleJson('catalog.json')..['min_app_version'] = 99;
    await pumpUi(
      tester,
      const HomeScreen(),
      overrides: uiOverrides(
        repository: FakeRepository(catalog: Catalog.fromJson(json)),
      ),
    );
    expect(
      find.widgetWithText(NoticeStrip, l10nOf(tester).updateRequired),
      findsOneWidget,
    );
  });

  group('where a market card leads', () {
    final catalog = sampleCatalog();
    BrochureGroups groups(String id) =>
        groupBrochures(catalog.brochuresOf(id), sampleToday);

    test('web-view chain opens its site', () {
      final a101 = catalog.chainById('a101')!;
      expect(
        chainDestination(a101, groups('a101')).destination,
        ChainDestination.web,
      );
    });

    test('a single brochure opens directly', () {
      final watsons = catalog.chainById('watsons')!;
      final target = chainDestination(watsons, groups('watsons'));
      expect(target.destination, ChainDestination.singleBrochure);
      expect(target.brochure!.id, 'watsons-2026-11-kasim-katalogu');
    });

    test('several brochures open the market screen', () {
      final bim = catalog.chainById('bim')!;
      expect(
        chainDestination(bim, groups('bim')).destination,
        ChainDestination.list,
      );
    });

    test('no brochure opens the market screen (its empty state)', () {
      expect(
        chainDestination(
          catalog.chainById('bim')!,
          const BrochureGroups(),
        ).destination,
        ChainDestination.list,
      );
    });
  });

  testWidgets('tapping BİM opens its market screen, Watsons its brochure', (
    tester,
  ) async {
    final image = await makeTestImage(tester);
    await pumpUi(
      tester,
      const HomeScreen(),
      overrides: uiOverrides(image: image),
      size: const Size(411, 3000),
    );

    await tester.tap(_card('bim'));
    await tester.pumpAndSettle();
    expect(find.byType(ChainScreen), findsOneWidget);

    await tester.tap(find.text(l10nOf(tester).back));
    await tester.pumpAndSettle();
    expect(find.byType(ChainScreen), findsNothing);

    await tester.tap(_card('watsons'));
    await tester.pumpAndSettle();
    expect(find.byType(BrochureScreen), findsOneWidget);
    expect(find.byType(ChainScreen), findsNothing);
  });
}
