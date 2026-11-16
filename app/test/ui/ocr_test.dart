// 3B.3: prices read from the brochure pages (OCR). The "Broşürden okundu"
// tag appears only on those prices, their page button names the page and
// opens it, the list starts with one short note, the search says what the
// tag means and opens the page, and nothing overflows with a huge font.

import 'package:aktuel_brosur/data/data.dart';
import 'package:aktuel_brosur/design/widgets/feedback.dart';
import 'package:aktuel_brosur/features/brochure/brochure_screen.dart';
import 'package:aktuel_brosur/features/brochure/viewer_controls.dart';
import 'package:aktuel_brosur/features/chain/brochure_card.dart';
import 'package:aktuel_brosur/features/products/product_card.dart';
import 'package:aktuel_brosur/features/search/search_result_card.dart';
import 'package:aktuel_brosur/features/search/search_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers.dart';
import 'support.dart';

const _sok = 'sok-2026-11-11-haftanin-firsatlari'; // 4 pages, 4 OCR prices
const _bim = 'bim-2026-11-13-cuma'; // 4 pages + written list
const _tag = ValueKey('ocr-tag');
const _note = ValueKey('ocr-list-note');
const _showOnPage = ValueKey('show-on-page');
const _input = ValueKey('search-input');
const _small = Size(320, 640);

const _ocrProduct = Product(
  name: 'Toz Deterjan',
  brand: 'Omo',
  quantityText: '6 kg',
  price: Money(129900),
  pageIndex: 3,
  source: ProductSource.ocr,
);

const _writtenProduct = Product(
  name: 'Toz Deterjan',
  brand: 'Omo',
  quantityText: '6 kg',
  price: Money(129900),
  pageIndex: 3,
);

String _indicator(WidgetTester tester) =>
    tester.widget<Text>(find.byKey(const ValueKey('viewer-indicator'))).data!;

Future<void> _card(
  WidgetTester tester,
  Product product, {
  VoidCallback? onShowPage,
  double textScale = 1,
  Size size = phoneSize,
  Brightness brightness = Brightness.light,
}) async {
  await pumpUi(
    tester,
    Scaffold(
      body: SingleChildScrollView(
        child: ProductCard(product: product, onShowPage: onShowPage),
      ),
    ),
    overrides: uiOverrides(),
    textScale: textScale,
    size: size,
    brightness: brightness,
  );
}

Future<void> _brochure(
  WidgetTester tester,
  String id, {
  double textScale = 1,
  Size size = phoneSize,
  Brightness brightness = Brightness.light,
}) async {
  final image = await makeTestImage(tester);
  await pumpUi(
    tester,
    BrochureScreen(brochureId: id),
    overrides: uiOverrides(image: image),
    textScale: textScale,
    size: size,
    brightness: brightness,
  );
  await tester.pump();
}

Future<void> _openProducts(WidgetTester tester) async {
  await tester.tap(find.byKey(const ValueKey('tab-products')));
  await tester.pumpAndSettle();
}

Future<void> _search(
  WidgetTester tester, {
  double textScale = 1,
  Size size = phoneSize,
  Brightness brightness = Brightness.light,
}) async {
  final image = await makeTestImage(tester);
  await pumpUi(
    tester,
    const SearchScreen(),
    overrides: uiOverrides(image: image),
    textScale: textScale,
    size: size,
    brightness: brightness,
  );
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 20));
  }
}

Future<void> _type(WidgetTester tester, String text) async {
  await tester.enterText(find.byKey(_input), text);
  await tester.pump();
}

void main() {
  group('product card', () {
    testWidgets('an OCR price carries the tag, right under the price', (
      tester,
    ) async {
      await _card(tester, _ocrProduct);
      final l10n = l10nOf(tester);
      final tag = find.byKey(_tag);
      expect(tag, findsOneWidget);
      expect(
        find.descendant(of: tag, matching: find.text(l10n.ocrTag)),
        findsOneWidget,
      );
      // Under the shelf price, not somewhere else on the card.
      final price = find.byKey(const ValueKey('shelf-price'));
      expect(
        tester.getTopLeft(tag).dy,
        greaterThan(tester.getBottomLeft(price).dy - 1),
      );
      expect(
        (tester.getTopLeft(tag).dx - tester.getTopLeft(price).dx).abs(),
        lessThan(1),
      );
      // Readable: 18 sp and up, not a red or yellow badge.
      final text = tester.widget<Text>(
        find.descendant(of: tag, matching: find.text(l10n.ocrTag)),
      );
      expect(text.style!.fontSize, greaterThanOrEqualTo(18));
      expect(find.byType(Pill), findsNothing);
    });

    testWidgets('a written price has no tag', (tester) async {
      await _card(tester, _writtenProduct);
      expect(find.byKey(_tag), findsNothing);
      expect(find.text(l10nOf(tester).ocrTag), findsNothing);
    });

    testWidgets('the OCR quantity is visible next to the price', (
      tester,
    ) async {
      await _card(tester, _ocrProduct);
      expect(find.text('6 kg'), findsOneWidget);
    });

    testWidgets('the OCR page button names the page and is 56 dp', (
      tester,
    ) async {
      var shown = 0;
      await _card(tester, _ocrProduct, onShowPage: () => shown++);
      final l10n = l10nOf(tester);
      final button = find.byKey(_showOnPage);
      expect(
        find.descendant(of: button, matching: find.text(l10n.ocrShowOnPage(4))),
        findsOneWidget,
      );
      expect(find.text(l10n.showOnPage), findsNothing);
      expect(tester.getSize(button).height, greaterThanOrEqualTo(56));
      await tester.tap(button);
      expect(shown, 1);
    });

    testWidgets('a written card keeps "Sayfada göster"', (tester) async {
      await _card(tester, _writtenProduct, onShowPage: () {});
      final l10n = l10nOf(tester);
      expect(find.text(l10n.showOnPage), findsOneWidget);
      expect(find.text(l10n.ocrShowOnPage(4)), findsNothing);
    });

    testWidgets('a screen reader hears the price and that it was read', (
      tester,
    ) async {
      final handle = tester.ensureSemantics();
      await _card(tester, _ocrProduct);
      final l10n = l10nOf(tester);
      final node = tester.getSemantics(
        find.byKey(const ValueKey('shelf-price')),
      );
      final label = node.label;
      expect(label, contains('Toz Deterjan'));
      expect(label, contains(l10n.priceWithUnit('1.299,00 ₺', '6 kg')));
      expect(label, contains(l10n.ocrTag));
      // The tag comes after the price it belongs to.
      expect(
        label.indexOf(l10n.ocrTag),
        greaterThan(label.indexOf('1.299,00 ₺')),
      );
      handle.dispose();
    });
  });

  group('brochure with prices read from its pages', () {
    testWidgets('shows the "Ürünler" tab and starts on the pages', (
      tester,
    ) async {
      await _brochure(tester, _sok);
      expect(find.byType(ModeTabs), findsOneWidget);
      expect(find.byType(ViewerControls), findsOneWidget);
      expect(find.byType(ProductCard), findsNothing);
    });

    testWidgets('the list opens with one note, every price tagged', (
      tester,
    ) async {
      await _brochure(tester, _sok, size: const Size(411, 2400));
      await _openProducts(tester);
      final l10n = l10nOf(tester);

      expect(find.byKey(_note), findsOneWidget);
      expect(find.text(l10n.ocrListNote), findsOneWidget);
      expect(find.byType(ProductCard), findsNWidgets(4));
      expect(find.byKey(_tag), findsNWidgets(4));
      // The note is above the first product.
      expect(
        tester.getTopLeft(find.byKey(_note)).dy,
        lessThan(tester.getTopLeft(find.byType(ProductCard).first).dy),
      );
      // Two "Lastik" told apart by their size.
      expect(find.text('Lastik'), findsNWidgets(2));
      expect(find.text('2 cm'), findsOneWidget);
      expect(find.text('3 cm'), findsOneWidget);
      // Every button names its page.
      expect(find.text(l10n.ocrShowOnPage(1)), findsOneWidget);
      expect(find.text(l10n.ocrShowOnPage(2)), findsNWidgets(2));
      expect(find.text(l10n.ocrShowOnPage(4)), findsOneWidget);
      expect(find.text(l10n.showOnPage), findsNothing);
    });

    testWidgets('"Broşürde gör, sayfa 4" opens page 4', (tester) async {
      await _brochure(tester, _sok, size: const Size(411, 2400));
      await _openProducts(tester);
      final l10n = l10nOf(tester);
      await tester.tap(find.text(l10n.ocrShowOnPage(4)));
      await tester.pumpAndSettle();
      expect(find.byType(ViewerControls).hitTestable(), findsOneWidget);
      expect(_indicator(tester), '4 / 4');
    });

    testWidgets('a written list (BİM) has no note and no tag', (tester) async {
      await _brochure(tester, _bim, size: const Size(411, 2400));
      await _openProducts(tester);
      expect(find.byType(ProductCard), findsWidgets);
      expect(find.byKey(_note), findsNothing);
      expect(find.byKey(_tag), findsNothing);
      expect(find.text(l10nOf(tester).showOnPage), findsWidgets);
    });

    testWidgets('the market screen card does not count OCR prices', (
      tester,
    ) async {
      await pumpUi(tester, const Scaffold(body: SizedBox()));
      final l10n = l10nOf(tester);
      final catalog = sampleCatalog();
      final sok = catalog.brochureById(_sok)!;
      expect(brochureDetail(l10n, sok), l10n.pageCount(4));
      final bim = catalog.brochureById(_bim)!;
      expect(
        brochureDetail(l10n, bim),
        l10n.pairWithDot(l10n.pageCount(4), l10n.productCount(14)),
      );
    });
  });

  group('search', () {
    testWidgets('an OCR result is tagged and says so to a screen reader', (
      tester,
    ) async {
      final handle = tester.ensureSemantics();
      await _search(tester);
      await _type(tester, 'omo');
      final l10n = l10nOf(tester);
      final card = find.byType(SearchResultCard);
      expect(card, findsOneWidget);
      expect(
        find.descendant(of: card, matching: find.byKey(_tag)),
        findsOneWidget,
      );
      expect(
        find.bySemanticsLabel(
          RegExp('Toz Deterjan, Omo, .*${l10n.ocrTag}, Şok, '),
        ),
        findsOneWidget,
      );
      expect(find.text(l10n.searchPriceNoteOcr), findsOneWidget);
      expect(find.text(l10n.searchPriceNote), findsNothing);
      handle.dispose();
    });

    testWidgets('a written result has no tag and the plain note', (
      tester,
    ) async {
      await _search(tester);
      await _type(tester, 'süt');
      final l10n = l10nOf(tester);
      expect(find.byType(SearchResultCard), findsOneWidget);
      expect(find.byKey(_tag), findsNothing);
      expect(find.text(l10n.searchPriceNote), findsOneWidget);
      expect(find.text(l10n.searchPriceNoteOcr), findsNothing);
    });

    testWidgets('an OCR result opens the brochure on its page', (tester) async {
      await _search(tester);
      await _type(tester, 'omo');
      await tester.tap(find.byType(SearchResultCard));
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));
      expect(find.byType(BrochureScreen), findsOneWidget);
      expect(find.byType(ViewerControls).hitTestable(), findsOneWidget);
      expect(_indicator(tester), '4 / 4');

      // Its "Ürünler" tab shows the searched product first, still tagged.
      await _openProducts(tester);
      final l10n = l10nOf(tester);
      final pinned = find.byKey(const ValueKey('searched-product'));
      expect(pinned, findsOneWidget);
      expect(
        find.descendant(of: pinned, matching: find.byKey(_tag)),
        findsOneWidget,
      );
      expect(find.byKey(_note), findsOneWidget);
      expect(
        tester.getTopLeft(find.byKey(_note)).dy,
        lessThan(tester.getTopLeft(pinned).dy),
      );
      expect(find.text(l10n.searchedProductTitle), findsOneWidget);
    });

    testWidgets('the texts no longer say every other market is a picture', (
      tester,
    ) async {
      await pumpUi(tester, const Scaffold(body: SizedBox()));
      final l10n = l10nOf(tester);
      for (final text in [
        l10n.searchCoverageNote,
        l10n.searchEmptyIndexMessage,
        l10n.searchPriceNoteOcr,
      ]) {
        expect(text, isNot(contains('resim')), reason: text);
        expect(text, isNot(contains('yazı olarak')), reason: text);
      }
      // The OCR note does not claim the price is exactly as printed.
      expect(l10n.searchPriceNoteOcr, isNot(contains('yazdığı gibidir')));
      expect(l10n.searchPriceNoteOcr, contains(l10n.ocrTag));
    });
  });

  group('no overflow', () {
    for (final scale in [1.0, 1.3, 2.0]) {
      for (final brightness in Brightness.values) {
        for (final size in [phoneSize, _small]) {
          final what =
              'font scale $scale, ${brightness.name}, '
              '${size.width.toInt()} dp';

          testWidgets('OCR list: $what', (tester) async {
            await _brochure(
              tester,
              _sok,
              textScale: scale,
              size: size,
              brightness: brightness,
            );
            await _openProducts(tester);
            expect(tester.takeException(), isNull);
            await tester.drag(
              find.byType(ListView).last,
              const Offset(0, -3000),
            );
            await tester.pump();
            expect(tester.takeException(), isNull, reason: 'scrolled');
          });

          testWidgets('OCR search result: $what', (tester) async {
            await _search(
              tester,
              textScale: scale,
              size: size,
              brightness: brightness,
            );
            await _type(tester, 'lastik');
            expect(tester.takeException(), isNull);
            await tester.drag(find.byType(ListView), const Offset(0, -3000));
            await tester.pump();
            expect(tester.takeException(), isNull, reason: 'scrolled');
          });
        }
      }
    }
  });
}
