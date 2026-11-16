// D3: "Broşürlerde ara". The home entry point, the search screen's states
// (before typing, loading, results, nothing found, offline / error) and the
// way a result opens its brochure.

import 'dart:async';

import 'package:aktuel_brosur/data/data.dart';
import 'package:aktuel_brosur/design/widgets/app_buttons.dart';
import 'package:aktuel_brosur/design/widgets/chain_mark.dart';
import 'package:aktuel_brosur/design/widgets/feedback.dart';
import 'package:aktuel_brosur/features/app/navigation.dart';
import 'package:aktuel_brosur/features/brochure/brochure_screen.dart';
import 'package:aktuel_brosur/features/home/home_screen.dart';
import 'package:aktuel_brosur/features/products/product_card.dart';
import 'package:aktuel_brosur/features/search/search_entry_button.dart';
import 'package:aktuel_brosur/features/search/search_result_card.dart';
import 'package:aktuel_brosur/features/search/search_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/misc.dart' show Override;
import 'package:flutter_test/flutter_test.dart';

import '../helpers.dart';
import 'support.dart';

const _input = ValueKey('search-input');
const _clear = ValueKey('search-clear');
const _shelf = ValueKey('shelf-price');
const _small = Size(320, 640);

/// Lets the catalog, the product files and the index futures complete.
/// (`pumpAndSettle` cannot be used while a spinner or a cursor is on screen.)
Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 20));
  }
}

Future<void> _open(
  WidgetTester tester, {
  List<Override>? overrides,
  double textScale = 1,
  Brightness brightness = Brightness.light,
  Size size = phoneSize,
  bool reduceMotion = false,
}) async {
  final image = await makeTestImage(tester);
  await pumpUi(
    tester,
    const SearchScreen(),
    overrides: overrides ?? uiOverrides(image: image),
    textScale: textScale,
    brightness: brightness,
    size: size,
    reduceMotion: reduceMotion,
  );
  await _settle(tester);
}

Future<void> _type(WidgetTester tester, String text) async {
  await tester.enterText(find.byKey(_input), text);
  await tester.pump();
}

Finder _result(int index) => find.byKey(ValueKey('search-result-$index'));

/// A made-up index for the cases the sample data does not have: a market
/// without a logo, a brochure that has not started, very long names.
final Chain _tkk = chain('tkkoop', name: 'Tarım Kredi Market');
final Chain _hakmar = chain('hakmar', name: 'Hakmar');

SearchIndex _fakeIndex() {
  final thisWeek = brochure(
    'tkkoop-1',
    chainId: 'tkkoop',
    from: d(2026, 11, 10),
    to: d(2026, 11, 16),
  );
  final nextWeek = brochure(
    'hakmar-1',
    chainId: 'hakmar',
    from: d(2026, 11, 18),
    to: d(2026, 11, 24),
  );
  return SearchIndex.fromHits(
    [
      SearchHit(
        chain: _tkk,
        brochure: thisWeek,
        product: const Product(
          name: 'Süt Tam Yağlı Uzun Ömürlü Kutu 1 L',
          brand: 'Tarım Kredi Birlik',
          price: Money(3450),
        ),
      ),
      SearchHit(
        chain: _hakmar,
        brochure: nextWeek,
        product: const Product(
          name: 'Süt Laktozsuz Yarım Yağlı Pastörize Cam Şişe',
          brand: 'Sütaş',
          quantityText: 'kg fiyatı',
          price: Money(179900),
          oldPrice: Money(199900),
          memberPrice: Money(149990),
          memberPriceLabel: 'Hakmar Kart sahiplerine özel fiyat',
          image: 'https://example.com/sut.png',
        ),
      ),
    ],
    [_tkk, _hakmar],
  );
}

List<Override> _fakeOverrides({SearchIndex? index, FakeRepository? repo}) => [
  ...uiOverrides(repository: repo),
  searchIndexProvider.overrideWith((ref) async => index ?? _fakeIndex()),
];

void main() {
  group('home entry point', () {
    testWidgets('one big "Ürün ara" button that opens the search', (
      tester,
    ) async {
      await pumpUi(tester, const HomeScreen(), overrides: uiOverrides());
      final l10n = l10nOf(tester);
      final entry = find.byType(SearchEntryButton);

      expect(entry, findsOneWidget);
      expect(
        find.descendant(of: entry, matching: find.text(l10n.searchTitle)),
        findsOneWidget,
      );
      // Big and wide: not an icon in a corner.
      final size = tester.getSize(entry);
      expect(size.height, greaterThanOrEqualTo(64));
      expect(size.width, greaterThan(phoneSize.width * 0.8));
      // It sits above the market question, so it is seen without scrolling.
      expect(
        tester.getTopLeft(entry).dy,
        lessThan(tester.getTopLeft(find.text(l10n.homeQuestion)).dy),
      );
      expect(find.bySemanticsLabel(l10n.searchEntrySpoken), findsOneWidget);

      await tester.tap(entry);
      await _settle(tester);
      expect(find.byType(SearchScreen), findsOneWidget);
      expect(find.text(l10n.back), findsOneWidget);
    });

    testWidgets('is left out while nothing is loaded yet', (tester) async {
      await pumpUi(
        tester,
        const HomeScreen(),
        overrides: uiOverrides(
          repository: FakeRepository(
            error: const CatalogUnavailableException('offline'),
          ),
        ),
      );
      expect(find.byType(SearchEntryButton), findsNothing);
    });
  });

  group('before typing', () {
    testWidgets('the keyboard is up and the field is large', (tester) async {
      await _open(tester);
      final l10n = l10nOf(tester);
      expect(tester.testTextInput.isVisible, isTrue);
      expect(find.text(l10n.searchFieldHint), findsOneWidget);
      final field = tester.widget<TextField>(find.byKey(_input));
      expect(field.style!.fontSize, greaterThanOrEqualTo(18));
      expect(
        find.bySemanticsLabel(RegExp(l10n.searchFieldSpoken)),
        findsOneWidget,
      );
      // Nothing to delete yet.
      expect(find.byKey(_clear), findsNothing);
    });

    testWidgets('example words are big buttons and only ones that find '
        'something', (tester) async {
      await _open(tester, overrides: null);
      final l10n = l10nOf(tester);
      expect(find.text(l10n.searchIdleTitle), findsOneWidget);
      expect(find.text(l10n.searchExamplesTitle), findsOneWidget);
      // In the sample brochures: süt, çay (bardağı), yağ, şeker, pirinç…
      for (final word in ['Süt', 'Çay', 'Yağ', 'Şeker']) {
        final chip = find.byKey(ValueKey('search-example-$word'));
        expect(chip, findsOneWidget, reason: word);
        expect(tester.getSize(chip).height, greaterThanOrEqualTo(56));
        expect(tester.getSize(chip).width, greaterThanOrEqualTo(56));
      }
      // ...but no peynir or yumurta, so those are not offered.
      expect(find.byKey(const ValueKey('search-example-Peynir')), findsNothing);
      expect(
        find.byKey(const ValueKey('search-example-Yumurta')),
        findsNothing,
      );
      expect(find.bySemanticsLabel(l10n.searchExampleSpoken('Süt')), findsOne);
    });

    testWidgets('says honestly which markets are searched', (tester) async {
      await _open(tester);
      final l10n = l10nOf(tester);
      expect(find.text(l10n.searchCoverageTitle), findsOneWidget);
      // BİM and Migros publish prices as text, Şok's were read from its
      // pages; Watsons has no price list.
      expect(find.byKey(const ValueKey('search-chain-bim')), findsOneWidget);
      expect(find.byKey(const ValueKey('search-chain-migros')), findsOneWidget);
      expect(find.byKey(const ValueKey('search-chain-sok')), findsOneWidget);
      expect(find.byKey(const ValueKey('search-chain-watsons')), findsNothing);
      expect(find.byType(ChainMark), findsNWidgets(3));
      expect(find.text(l10n.searchCoverageNote), findsOneWidget);
      // Şok's prices can show up, so the note explains their tag.
      expect(find.text(l10n.searchPriceNoteOcr), findsOneWidget);
      expect(find.text(l10n.searchPriceNote), findsNothing);
    });

    testWidgets('tapping an example searches for it', (tester) async {
      await _open(tester);
      await tester.tap(find.byKey(const ValueKey('search-example-Süt')));
      await tester.pump();
      expect(
        tester.widget<TextField>(find.byKey(_input)).controller!.text,
        'Süt',
      );
      expect(find.byType(SearchResultCard), findsOneWidget);
      expect(find.text('Tam Yağlı Süt'), findsOneWidget);
    });

    testWidgets('one letter asks for one more', (tester) async {
      await _open(tester);
      await _type(tester, 's');
      final l10n = l10nOf(tester);
      expect(find.text(l10n.searchTooShort), findsOneWidget);
      expect(find.byType(SearchResultCard), findsNothing);
    });
  });

  group('results', () {
    testWidgets('cheapest first, with market, dates and the honesty note', (
      tester,
    ) async {
      await _open(tester, size: const Size(411, 2400));
      await _type(tester, 'ayçiçek');
      final l10n = l10nOf(tester);

      expect(find.byType(SearchResultCard), findsNWidgets(3));
      expect(find.text(l10n.searchResultCount(3)), findsOneWidget);
      expect(find.text(l10n.searchSortNote), findsOneWidget);
      // Şok's 349,90 ₺ was read from its page: the note says what that means.
      expect(find.text(l10n.searchPriceNoteOcr), findsOneWidget);

      // BİM 319,50 ₺ is above Migros 329,95 ₺, Şok 349,90 ₺ last.
      final bim = _result(0);
      final migros = _result(1);
      expect(
        find.descendant(of: bim, matching: find.text('319,50 ₺')),
        findsOneWidget,
      );
      expect(
        find.descendant(of: migros, matching: find.text('329,95 ₺')),
        findsOneWidget,
      );
      expect(tester.getTopLeft(bim).dy, lessThan(tester.getTopLeft(migros).dy));
      // Each result names its market and its brochure's dates.
      expect(
        find.descendant(of: bim, matching: find.text('BİM')),
        findsOneWidget,
      );
      expect(
        find.descendant(of: bim, matching: find.text('13 Kasım Cuma')),
        findsOneWidget,
      );
      // ("Migros" is also this product's brand, so ask for the market line.)
      expect(
        tester
            .widget<Text>(
              find.descendant(
                of: migros,
                matching: find.byKey(const ValueKey('result-chain')),
              ),
            )
            .data,
        'Migros',
      );
      expect(
        find.descendant(of: migros, matching: find.text('12–25 Kasım')),
        findsOneWidget,
      );
      expect(
        find.descendant(of: _result(2), matching: find.text('349,90 ₺')),
        findsOneWidget,
      );
      expect(find.byType(ChainMark), findsNWidgets(3));
      // The list ends by saying what was (and was not) searched.
      expect(
        find.text(l10n.searchNoResultsCoverage('BİM, Şok, Migros')),
        findsOneWidget,
      );
    });

    testWidgets('typing without Turkish letters finds the same', (
      tester,
    ) async {
      await _open(tester, size: const Size(411, 2400));
      await _type(tester, 'AYCICEK yagi');
      expect(find.byType(SearchResultCard), findsNWidgets(3));
    });

    testWidgets('a member price follows section 14: shelf price biggest, '
        'labelled tag below', (tester) async {
      await _open(tester);
      await _type(tester, 'buğday');
      final card = _result(0);
      final tag = find.descendant(
        of: card,
        matching: find.byType(MemberPriceTag),
      );
      expect(tag, findsOneWidget);
      expect(
        find.descendant(of: tag, matching: find.text('Money ile')),
        findsOneWidget,
      );
      final shelf = tester.widget<Text>(
        find.descendant(of: find.byKey(_shelf), matching: find.text('99,95 ₺')),
      );
      final member = tester.widget<Text>(
        find.descendant(of: tag, matching: find.text('77,95 ₺')),
      );
      expect(shelf.style!.fontSize, greaterThan(member.style!.fontSize!));
      expect(shelf.style!.decoration, isNot(TextDecoration.lineThrough));
      expect(
        tester.getTopLeft(find.byKey(_shelf)).dy,
        lessThan(tester.getTopLeft(tag).dy),
      );
      // The shelf price is not inside the tag, and no discount is claimed.
      expect(
        find.descendant(of: tag, matching: find.text('99,95 ₺')),
        findsNothing,
      );
      expect(
        find.descendant(of: card, matching: find.byType(Pill)),
        findsNothing,
      );
    });

    testWidgets('the unit note stays glued to the price', (tester) async {
      await _open(tester);
      await _type(tester, 'siirt');
      expect(find.text('1.799,00 ₺'), findsOneWidget);
      // Beside the shelf price and inside the member tag.
      expect(find.text('kg fiyatı'), findsNWidgets(2));
    });

    testWidgets('a screen reader hears product, price, market and dates as '
        'one button', (tester) async {
      await _open(tester);
      await _type(tester, 'buğday');
      final l10n = l10nOf(tester);
      final label =
          'Tam Buğday Ekmeği 400 g, Untad, 99,95 ₺, Money ile: 77,95 ₺, '
          'Migros, 12–25 Kasım, ${l10n.searchOpenSpoken}';
      expect(find.bySemanticsLabel(label), findsOneWidget);
    });

    testWidgets('a brochure that has not started says so', (tester) async {
      await _open(
        tester,
        overrides: _fakeOverrides(),
        size: const Size(411, 2400),
      );
      await _type(tester, 'süt');
      final l10n = l10nOf(tester);
      expect(find.byType(SearchResultCard), findsNWidgets(2));
      // Hakmar's brochure starts on the 18th; today is the 13th.
      expect(
        find.descendant(
          of: _result(1),
          matching: find.text(l10n.searchUpcoming),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: _result(0),
          matching: find.text(l10n.searchUpcoming),
        ),
        findsNothing,
      );
      expect(
        find.bySemanticsLabel(RegExp(l10n.searchUpcoming)),
        findsOneWidget,
      );
    });

    testWidgets('the clear button is 56 dp and empties the field', (
      tester,
    ) async {
      await _open(tester);
      await _type(tester, 'süt');
      final l10n = l10nOf(tester);
      final clear = find.byKey(_clear);
      expect(clear, findsOneWidget);
      expect(tester.getSize(clear).width, greaterThanOrEqualTo(56));
      expect(tester.getSize(clear).height, greaterThanOrEqualTo(56));
      expect(find.bySemanticsLabel(l10n.searchClear), findsOneWidget);

      await tester.tap(clear);
      await tester.pump();
      expect(tester.widget<TextField>(find.byKey(_input)).controller!.text, '');
      expect(find.byType(SearchResultCard), findsNothing);
      expect(find.text(l10n.searchIdleTitle), findsOneWidget);
      expect(find.byKey(_clear), findsNothing);
    });
  });

  group('opening a result', () {
    testWidgets('a product list brochure shows the product first', (
      tester,
    ) async {
      await _open(tester, size: const Size(411, 2400));
      await _type(tester, 'buğday');
      await tester.tap(_result(0));
      await tester.pumpAndSettle();
      final l10n = l10nOf(tester);

      expect(find.byType(BrochureScreen), findsOneWidget);
      expect(find.text(l10n.searchedProductTitle), findsOneWidget);
      expect(find.text(l10n.allProductsTitle), findsOneWidget);
      final pinned = find.byKey(const ValueKey('searched-product'));
      expect(
        find.descendant(
          of: pinned,
          matching: find.text('Tam Buğday Ekmeği 400 g'),
        ),
        findsOneWidget,
      );
      expect(tester.widget<ProductCard>(pinned).highlighted, isTrue);
      // It is above the heading of the full list.
      expect(
        tester.getTopLeft(pinned).dy,
        lessThan(tester.getTopLeft(find.text(l10n.allProductsTitle)).dy),
      );

      // "Geri" returns to the results, text still in the field.
      await tester.tap(find.text(l10n.back));
      await tester.pumpAndSettle();
      expect(find.byType(BrochureScreen), findsNothing);
      expect(find.byType(SearchResultCard), findsOneWidget);
    });

    testWidgets('a brochure with pages opens on the page that prints it', (
      tester,
    ) async {
      await _open(tester, size: const Size(411, 2400));
      await _type(tester, 'toz şeker');
      await tester.tap(_result(0));
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));
      expect(find.byType(BrochureScreen), findsOneWidget);
      // BİM's sample product is on the second of four pages.
      expect(
        tester
            .widget<Text>(find.byKey(const ValueKey('viewer-indicator')))
            .data,
        '2 / 4',
      );
    });

    test('the page is used only when the brochure really has it', () {
      final withPages = brochure('b1'); // one page
      SearchHit hit(Brochure b, int? page) => SearchHit(
        chain: _tkk,
        brochure: b,
        product: Product(name: 'x', price: const Money(100), pageIndex: page),
      );
      expect(searchHitPage(hit(withPages, 0)), 0);
      expect(searchHitPage(hit(withPages, 5)), isNull);
      expect(searchHitPage(hit(withPages, null)), isNull);
    });

    testWidgets('a product that left the list is not pinned', (tester) async {
      final image = await makeTestImage(tester);
      await pumpUi(
        tester,
        const BrochureScreen(
          brochureId: 'migros-910',
          focusProduct: Product(name: 'Artık yok', price: Money(100)),
        ),
        overrides: uiOverrides(image: image),
      );
      await tester.pumpAndSettle();
      final l10n = l10nOf(tester);
      expect(find.text(l10n.searchedProductTitle), findsNothing);
      expect(find.text('Artık yok'), findsNothing);
      expect(find.text(l10n.productCount(10)), findsOneWidget);
    });
  });

  group('other states', () {
    testWidgets('loading says what is being prepared', (tester) async {
      final never = Completer<SearchIndex>();
      await _open(
        tester,
        overrides: [
          ...uiOverrides(),
          searchIndexProvider.overrideWith((ref) => never.future),
        ],
      );
      final l10n = l10nOf(tester);
      expect(find.text(l10n.searchLoading), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      // The field is already usable.
      expect(tester.testTextInput.isVisible, isTrue);
    });

    testWidgets('nothing found: says where it looked and where it cannot', (
      tester,
    ) async {
      await _open(tester);
      await _type(tester, 'kivi');
      final l10n = l10nOf(tester);
      expect(find.text(l10n.searchNoResultsTitle('kivi')), findsOneWidget);
      expect(find.text(l10n.searchNoResultsMessage), findsOneWidget);
      expect(
        find.text(l10n.searchNoResultsCoverage('BİM, Şok, Migros')),
        findsOneWidget,
      );
      final again = find.widgetWithText(AppButton, l10n.searchNewSearch);
      expect(tester.getSize(again).height, greaterThanOrEqualTo(56));

      await tester.tap(again);
      await tester.pump();
      expect(find.text(l10n.searchIdleTitle), findsOneWidget);
      expect(tester.widget<TextField>(find.byKey(_input)).controller!.text, '');
    });

    testWidgets('no internet and nothing saved: plain words and a retry', (
      tester,
    ) async {
      final repository = FakeRepository(
        error: const CatalogUnavailableException('offline'),
      );
      await _open(tester, overrides: uiOverrides(repository: repository));
      final l10n = l10nOf(tester);
      expect(find.text(l10n.searchErrorTitle), findsOneWidget);
      expect(find.text(l10n.checkConnection), findsOneWidget);
      final retry = find.widgetWithText(AppButton, l10n.retry);
      expect(tester.getSize(retry).height, greaterThanOrEqualTo(56));

      repository.error = null;
      await tester.tap(retry);
      await _settle(tester);
      expect(find.text(l10n.searchErrorTitle), findsNothing);
      expect(find.text(l10n.searchIdleTitle), findsOneWidget);
    });

    testWidgets('offline with saved brochures: a calm notice, search works', (
      tester,
    ) async {
      await _open(
        tester,
        overrides: uiOverrides(repository: FakeRepository(isStale: true)),
        size: const Size(411, 2400),
      );
      final l10n = l10nOf(tester);
      expect(
        find.widgetWithText(NoticeStrip, l10n.searchOfflineNotice),
        findsOneWidget,
      );
      await _type(tester, 'süt');
      expect(find.byType(SearchResultCard), findsOneWidget);
      expect(
        find.widgetWithText(NoticeStrip, l10n.searchOfflineNotice),
        findsOneWidget,
      );
    });

    testWidgets('offline and no product list saved: says why', (tester) async {
      await _open(
        tester,
        overrides: uiOverrides(
          repository: FakeRepository(
            isStale: true,
            productsError: const ProductsUnavailableException('offline'),
          ),
        ),
      );
      final l10n = l10nOf(tester);
      expect(find.text(l10n.searchErrorTitle), findsOneWidget);
      expect(find.text(l10n.searchOfflineEmptyMessage), findsOneWidget);
      expect(find.widgetWithText(AppButton, l10n.retry), findsOneWidget);
    });

    testWidgets('no market publishes prices as text: says so', (tester) async {
      await _open(
        tester,
        overrides: _fakeOverrides(
          index: SearchIndex.fromHits(const [], const []),
        ),
      );
      final l10n = l10nOf(tester);
      expect(find.text(l10n.searchEmptyIndexTitle), findsOneWidget);
      expect(find.text(l10n.searchEmptyIndexMessage), findsOneWidget);
    });

    testWidgets('builds without motion when the system asks for it', (
      tester,
    ) async {
      await _open(tester, reduceMotion: true);
      await _type(tester, 'süt');
      expect(find.byType(SearchResultCard), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });

  group('no overflow', () {
    for (final scale in [1.0, 1.3, 2.0]) {
      for (final brightness in Brightness.values) {
        for (final size in [phoneSize, _small]) {
          final what =
              'font scale $scale, ${brightness.name}, '
              '${size.width.toInt()} dp';

          testWidgets('search states: $what', (tester) async {
            // Sample data: idle (examples, markets), results, nothing found.
            await _open(
              tester,
              textScale: scale,
              brightness: brightness,
              size: size,
            );
            expect(tester.takeException(), isNull, reason: 'idle');
            await tester.drag(find.byType(ListView), const Offset(0, -3000));
            await tester.pump();
            expect(tester.takeException(), isNull, reason: 'idle, scrolled');

            for (final query in ['s', 'süt', 'ayçiçek', 'kivi meyvesi']) {
              await _type(tester, query);
              expect(tester.takeException(), isNull, reason: query);
              await tester.drag(find.byType(ListView), const Offset(0, -3000));
              await tester.pump();
              expect(tester.takeException(), isNull, reason: '$query, end');
            }
          });

          testWidgets('long names, name plates, three prices: $what', (
            tester,
          ) async {
            await _open(
              tester,
              overrides: _fakeOverrides(),
              textScale: scale,
              brightness: brightness,
              size: size,
            );
            expect(tester.takeException(), isNull, reason: 'idle');
            await _type(tester, 'süt');
            expect(tester.takeException(), isNull, reason: 'results');
            expect(find.byType(SearchResultCard), findsWidgets);
            for (var i = 0; i < 4; i++) {
              await tester.drag(find.byType(ListView), const Offset(0, -500));
              await tester.pump();
              expect(tester.takeException(), isNull, reason: 'scroll $i');
            }
          });
        }
      }
    }

    testWidgets('with the keyboard open on a small screen and a huge font', (
      tester,
    ) async {
      tester.view.viewInsets = const FakeViewPadding(bottom: 300);
      await _open(tester, textScale: 2, size: _small);
      expect(tester.takeException(), isNull);
      await _type(tester, 'süt');
      expect(tester.takeException(), isNull);
      await _type(tester, 'kivi');
      expect(tester.takeException(), isNull);
      // The field is still fully on screen above the keyboard.
      expect(tester.getRect(find.byKey(_input)).bottom, lessThan(640 - 300));
    });

    testWidgets('the pinned product in a brochure list, huge font', (
      tester,
    ) async {
      final image = await makeTestImage(tester);
      final bread = ProductFile.parse(sampleText('products/migros-910.json'))
          .products
          .firstWhere((p) => p.hasMemberPrice);
      await pumpUi(
        tester,
        BrochureScreen(brochureId: 'migros-910', focusProduct: bread),
        overrides: uiOverrides(image: image),
        textScale: 2,
        size: _small,
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.byKey(const ValueKey('searched-product')), findsOneWidget);
    });
  });
}
