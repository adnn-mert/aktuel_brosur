// D2: the member price on a product card, the unit note beside a price, and
// jumping to a page in a long catalog.

import 'package:aktuel_brosur/data/data.dart';
import 'package:aktuel_brosur/design/widgets/app_buttons.dart';
import 'package:aktuel_brosur/design/widgets/feedback.dart';
import 'package:aktuel_brosur/features/brochure/brochure_screen.dart';
import 'package:aktuel_brosur/features/brochure/page_picker_screen.dart';
import 'package:aktuel_brosur/features/products/product_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support.dart';

const _shelfKey = ValueKey('shelf-price');
const _oldKey = ValueKey('old-price');

const _member = Product(
  name: 'Tam Buğday Ekmeği 400 g',
  brand: 'Untad',
  price: Money(9995),
  memberPrice: Money(7795),
  memberPriceLabel: 'Money ile',
);

const _threePrices = Product(
  name: 'Kişisel Bakım Havlusu 100\'lü',
  brand: 'Sleepy',
  price: Money(15995),
  oldPrice: Money(19995),
  memberPrice: Money(9995),
  memberPriceLabel: 'Money ile',
  image: 'https://example.com/havlu.png',
);

const _perKilo = Product(
  name: 'Siirt Fıstığı Tuzlu Kavrulmuş',
  quantityText: 'kg fiyatı',
  price: Money(179900),
  memberPrice: Money(149990),
  memberPriceLabel: 'Money ile',
);

const _plain = Product(name: 'Ayçiçek Yağı 5 L', price: Money(32995));

Future<void> _pumpCard(
  WidgetTester tester,
  Product product, {
  double textScale = 1,
  Brightness brightness = Brightness.light,
  Size size = phoneSize,
}) async {
  final image = await makeTestImage(tester);
  await pumpUi(
    tester,
    Scaffold(
      body: SingleChildScrollView(child: ProductCard(product: product)),
    ),
    overrides: uiOverrides(image: image),
    textScale: textScale,
    brightness: brightness,
    size: size,
  );
}

Text _textIn(WidgetTester tester, Finder scope, String text) =>
    tester.widget<Text>(find.descendant(of: scope, matching: find.text(text)));

String _indicator(WidgetTester tester) =>
    tester.widget<Text>(find.byKey(const ValueKey('viewer-indicator'))).data!;

void main() {
  group('member price', () {
    testWidgets('shows both prices; the member price carries its label', (
      tester,
    ) async {
      await _pumpCard(tester, _member);
      final tag = find.byType(MemberPriceTag);
      expect(tag, findsOneWidget);

      // Label and member price live inside the same framed tag...
      expect(
        find.descendant(of: tag, matching: find.text('Money ile')),
        findsOneWidget,
      );
      expect(
        find.descendant(of: tag, matching: find.text('77,95 ₺')),
        findsOneWidget,
      );
      // ...and the label is right next to the number (same box, a few dp).
      final label = tester.getRect(find.text('Money ile'));
      final price = tester.getRect(find.text('77,95 ₺'));
      final box = tester.getRect(tag);
      expect(box.contains(label.center) && box.contains(price.center), isTrue);
      expect(price.top - label.bottom, lessThan(8));

      // The shelf price is still there, outside the tag, plainly readable.
      final shelf = find.byKey(_shelfKey);
      expect(
        find.descendant(of: shelf, matching: find.text('99,95 ₺')),
        findsOneWidget,
      );
      expect(
        find.descendant(of: tag, matching: find.text('99,95 ₺')),
        findsNothing,
      );
    });

    testWidgets('the shelf price is never crossed out and stays the largest', (
      tester,
    ) async {
      await _pumpCard(tester, _member);
      final shelf = _textIn(tester, find.byKey(_shelfKey), '99,95 ₺');
      final member = _textIn(tester, find.byType(MemberPriceTag), '77,95 ₺');

      expect(shelf.style!.decoration, isNot(TextDecoration.lineThrough));
      expect(member.style!.decoration, isNot(TextDecoration.lineThrough));
      expect(shelf.style!.fontSize, greaterThan(member.style!.fontSize!));
      expect(member.style!.fontSize, greaterThanOrEqualTo(18));
      // Shelf price first (above), member price below it.
      expect(
        tester.getTopLeft(find.byKey(_shelfKey)).dy,
        lessThan(tester.getTopLeft(find.byType(MemberPriceTag)).dy),
      );
      // No discount pill: a member price is not a discount on the shelf price.
      expect(find.byType(Pill), findsNothing);
    });

    testWidgets('a screen reader hears the label together with the price', (
      tester,
    ) async {
      await _pumpCard(tester, _member);
      expect(
        find.bySemanticsLabel(RegExp('Money ile: 77,95 ₺')),
        findsOneWidget,
      );
    });

    testWidgets('three prices on one card keep three different looks', (
      tester,
    ) async {
      await _pumpCard(tester, _threePrices);
      final l10n = l10nOf(tester);

      final shelf = _textIn(tester, find.byKey(_shelfKey), '159,95 ₺');
      final old = tester.widget<Text>(find.byKey(_oldKey));
      final member = _textIn(tester, find.byType(MemberPriceTag), '99,95 ₺');

      expect(old.data, '199,95 ₺');
      expect(old.style!.decoration, TextDecoration.lineThrough);
      expect(shelf.style!.decoration, isNot(TextDecoration.lineThrough));
      expect(member.style!.decoration, isNot(TextDecoration.lineThrough));
      expect(shelf.style!.fontSize, greaterThan(member.style!.fontSize!));
      expect(member.style!.fontSize, greaterThan(old.style!.fontSize!));
      // The discount is old → shelf (20 %), not old → member (50 %).
      expect(find.text(l10n.discountPercent(20)), findsOneWidget);
      // The old price is outside the member tag.
      expect(
        find.descendant(
          of: find.byType(MemberPriceTag),
          matching: find.byKey(_oldKey),
        ),
        findsNothing,
      );
      expect(tester.takeException(), isNull);
    });

    testWidgets('a product without a member price looks as before', (
      tester,
    ) async {
      await _pumpCard(tester, _plain);
      expect(find.byType(MemberPriceTag), findsNothing);
      expect(find.text('329,95 ₺'), findsOneWidget);
      expect(find.text('Money ile'), findsNothing);
    });

    testWidgets('a member price without its label is not shown at all', (
      tester,
    ) async {
      // The model drops an unlabelled member price; the card must not find
      // a way to show it.
      const unlabelled = Product(
        name: 'Etiketsiz',
        price: Money(9995),
        memberPrice: Money(7795),
      );
      await _pumpCard(tester, unlabelled);
      expect(find.byType(MemberPriceTag), findsNothing);
      expect(find.text('77,95 ₺'), findsNothing);
      expect(find.text('99,95 ₺'), findsOneWidget);
    });

    for (final scale in [1.0, 2.0]) {
      for (final brightness in Brightness.values) {
        for (final size in [phoneSize, const Size(320, 640)]) {
          testWidgets('no overflow: font scale $scale, ${brightness.name}, '
              '${size.width.toInt()} dp', (tester) async {
            for (final product in [_member, _threePrices, _perKilo]) {
              await _pumpCard(
                tester,
                product,
                textScale: scale,
                brightness: brightness,
                size: size,
              );
              expect(tester.takeException(), isNull, reason: product.name);
              expect(find.byType(MemberPriceTag), findsOneWidget);
            }
          });
        }
      }
    }

    testWidgets('the Migros sample list marks its three member prices', (
      tester,
    ) async {
      final image = await makeTestImage(tester);
      await pumpUi(
        tester,
        const BrochureScreen(brochureId: 'migros-910'),
        overrides: uiOverrides(image: image),
        size: const Size(411, 4000),
      );
      await tester.pumpAndSettle();
      expect(find.byType(MemberPriceTag), findsNWidgets(3));
      expect(find.text('Money ile'), findsNWidgets(3));
      expect(find.text('1.499,90 ₺'), findsOneWidget);
      expect(find.text('1.799,00 ₺'), findsOneWidget);
    });
  });

  group('unit note', () {
    testWidgets('"kg fiyatı" is glued to every price it applies to', (
      tester,
    ) async {
      await _pumpCard(tester, _perKilo);
      // Once beside the shelf price, once inside the member tag.
      expect(find.text('kg fiyatı'), findsNWidgets(2));
      for (final (scope, price) in [
        (find.byKey(_shelfKey), '1.799,00 ₺'),
        (find.byType(MemberPriceTag), '1.499,90 ₺'),
      ]) {
        final unit = find.descendant(
          of: scope,
          matching: find.text('kg fiyatı'),
        );
        expect(unit, findsOneWidget);
        final priceRect = tester.getRect(
          find.descendant(of: scope, matching: find.text(price)),
        );
        final unitRect = tester.getRect(unit);
        // Same line, directly after the number.
        expect(unitRect.left - priceRect.right, inInclusiveRange(0, 12));
        expect(unitRect.bottom, closeTo(priceRect.bottom, 6));
      }
      // Read as one phrase.
      expect(
        find.bySemanticsLabel(RegExp('1.799,00 ₺, kg fiyatı')),
        findsOneWidget,
      );
    });

    testWidgets('with a very large font the note stays with its price', (
      tester,
    ) async {
      await _pumpCard(
        tester,
        _perKilo,
        textScale: 2,
        size: const Size(320, 640),
      );
      final price = tester.getRect(
        find.descendant(
          of: find.byKey(_shelfKey),
          matching: find.text('1.799,00 ₺'),
        ),
      );
      final unit = tester.getRect(
        find.descendant(
          of: find.byKey(_shelfKey),
          matching: find.text('kg fiyatı'),
        ),
      );
      // Wrapped below, but still the very next thing after the price.
      expect(unit.top - price.bottom, lessThan(8));
      expect(tester.takeException(), isNull);
    });

    testWidgets('no unit leaves no gap', (tester) async {
      await _pumpCard(tester, _member);
      final withBrand = tester.getSize(find.byType(ProductCard)).height;
      expect(
        find.descendant(of: find.byKey(_shelfKey), matching: find.byType(Wrap)),
        findsNothing,
      );
      // And a product with neither brand nor unit is shorter still.
      await _pumpCard(
        tester,
        const Product(
          name: 'Tam Buğday Ekmeği 400 g',
          price: Money(9995),
          memberPrice: Money(7795),
          memberPriceLabel: 'Money ile',
        ),
      );
      expect(
        tester.getSize(find.byType(ProductCard)).height,
        lessThan(withBrand),
      );
    });
  });

  group('page picker', () {
    const watsons = 'watsons-2026-11-kasim-katalogu'; // 46 pages
    const bim = 'bim-2026-11-13-cuma'; // 4 pages

    Future<void> open(
      WidgetTester tester,
      String id, {
      double textScale = 1,
      Size size = phoneSize,
    }) async {
      final image = await makeTestImage(tester);
      await pumpUi(
        tester,
        BrochureScreen(brochureId: id),
        overrides: uiOverrides(image: image),
        textScale: textScale,
        size: size,
      );
      await tester.pump();
    }

    testWidgets('a short brochure keeps the plain indicator', (tester) async {
      await open(tester, bim);
      expect(_indicator(tester), '1 / 4');
      expect(find.byKey(const ValueKey('viewer-pick-page')), findsNothing);
      await tester.tap(find.byKey(const ValueKey('viewer-indicator')));
      await tester.pumpAndSettle();
      expect(find.byType(PagePickerScreen), findsNothing);
    });

    testWidgets('a long catalog: the indicator is a 56 dp button', (
      tester,
    ) async {
      await open(tester, watsons);
      final l10n = l10nOf(tester);
      final button = find.byKey(const ValueKey('viewer-pick-page'));
      expect(button, findsOneWidget);
      expect(tester.getSize(button).height, greaterThanOrEqualTo(56));
      expect(tester.getSize(button).width, greaterThanOrEqualTo(56));
      expect(
        find.bySemanticsLabel(l10n.pagePickerOpenSpoken(1, 46)),
        findsOneWidget,
      );
    });

    testWidgets('choosing a number jumps straight to that page', (
      tester,
    ) async {
      await open(tester, watsons);
      final l10n = l10nOf(tester);

      await tester.tap(find.byKey(const ValueKey('viewer-pick-page')));
      await tester.pumpAndSettle();
      expect(find.byType(PagePickerScreen), findsOneWidget);
      expect(find.text(l10n.pagePickerTitle), findsOneWidget);
      expect(find.text(l10n.back), findsOneWidget);
      // Every page has a button; the current one says so.
      for (final page in [1, 2, 23, 46]) {
        expect(find.byKey(ValueKey('pick-page-$page')), findsOneWidget);
      }
      expect(
        find.bySemanticsLabel(l10n.pageNumberCurrentSpoken(1)),
        findsOneWidget,
      );
      for (final page in [1, 23]) {
        final size = tester.getSize(find.byKey(ValueKey('pick-page-$page')));
        expect(size.width, greaterThanOrEqualTo(56));
        expect(size.height, greaterThanOrEqualTo(56));
      }

      await tester.ensureVisible(find.byKey(const ValueKey('pick-page-23')));
      await tester.tap(find.byKey(const ValueKey('pick-page-23')));
      await tester.pumpAndSettle();
      expect(find.byType(PagePickerScreen), findsNothing);
      expect(_indicator(tester), '23 / 46');

      // Opening it again marks the new position.
      await tester.tap(find.byKey(const ValueKey('viewer-pick-page')));
      await tester.pumpAndSettle();
      expect(
        find.bySemanticsLabel(l10n.pageNumberCurrentSpoken(23)),
        findsOneWidget,
      );
    });

    testWidgets('"Geri" leaves the picker without changing the page', (
      tester,
    ) async {
      await open(tester, watsons);
      await tester.tap(find.byKey(const ValueKey('viewer-next')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('viewer-pick-page')));
      await tester.pumpAndSettle();
      await tester.tap(find.text(l10nOf(tester).back));
      await tester.pumpAndSettle();
      expect(find.byType(PagePickerScreen), findsNothing);
      expect(_indicator(tester), '2 / 46');
    });

    testWidgets('jumping resets the zoom so the new page is seen whole', (
      tester,
    ) async {
      await open(tester, watsons);
      await tester.tap(find.byKey(const ValueKey('viewer-zoom-in')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('viewer-pick-page')));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.byKey(const ValueKey('pick-page-10')));
      await tester.tap(find.byKey(const ValueKey('pick-page-10')));
      await tester.pumpAndSettle();
      expect(_indicator(tester), '10 / 46');
      // Zoom-out is off again: the page is at its fitted size.
      final zoomOut = find.byKey(const ValueKey('viewer-zoom-out'));
      expect(tester.widget<AppIconButton>(zoomOut).onPressed, isNull);
    });

    for (final scale in [1.0, 2.0]) {
      for (final size in [phoneSize, const Size(320, 640)]) {
        testWidgets('no overflow in bar and picker '
            '(font scale $scale, ${size.width.toInt()} dp)', (tester) async {
          await open(tester, watsons, textScale: scale, size: size);
          expect(tester.takeException(), isNull);
          await tester.tap(find.byKey(const ValueKey('viewer-pick-page')));
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull);
          await tester.drag(
            find.byType(SingleChildScrollView),
            const Offset(0, -4000),
          );
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull);
          final last = find.byKey(const ValueKey('pick-page-46'));
          expect(tester.getSize(last).width, greaterThanOrEqualTo(56));
        });
      }
    }
  });
}
