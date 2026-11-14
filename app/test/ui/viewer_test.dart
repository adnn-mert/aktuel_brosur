import 'package:aktuel_brosur/design/widgets/app_buttons.dart';
import 'package:aktuel_brosur/design/widgets/feedback.dart';
import 'package:aktuel_brosur/features/brochure/brochure_screen.dart';
import 'package:aktuel_brosur/features/brochure/viewer_controls.dart';
import 'package:aktuel_brosur/features/brochure/zoomable_page.dart';
import 'package:aktuel_brosur/features/products/product_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support.dart';

const _bimBoth = 'bim-2026-11-13-cuma'; // 4 pages + 14 products
const _sok = 'sok-2026-11-11-haftanin-firsatlari'; // pages are missing assets
const _migros = 'migros-910'; // products only

AppIconButton _button(WidgetTester tester, String key) =>
    tester.widget<AppIconButton>(find.byKey(ValueKey(key)));

String _indicator(WidgetTester tester) =>
    tester.widget<Text>(find.byKey(const ValueKey('viewer-indicator'))).data!;

/// Scale of the page that is on screen.
double _scale(WidgetTester tester) => tester
    .widget<InteractiveViewer>(
      find.descendant(
        of: find.byKey(const ValueKey('page-0')),
        matching: find.byType(InteractiveViewer),
      ),
    )
    .transformationController!
    .value
    .getMaxScaleOnAxis();

Future<void> _open(
  WidgetTester tester,
  String brochureId, {
  double textScale = 1,
  bool imagesFail = false,
  bool reduceMotion = false,
  Size size = phoneSize,
}) async {
  final image = await makeTestImage(tester);
  await pumpUi(
    tester,
    BrochureScreen(brochureId: brochureId),
    overrides: uiOverrides(image: image, imagesFail: imagesFail),
    textScale: textScale,
    reduceMotion: reduceMotion,
    size: size,
  );
  await tester.pump();
}

void main() {
  testWidgets('controls: arrows, "1 / 4", + and − are all visible and big', (
    tester,
  ) async {
    await _open(tester, _bimBoth);
    final l10n = l10nOf(tester);

    expect(_indicator(tester), '1 / 4');
    expect(find.bySemanticsLabel(l10n.pagePrevious), findsOneWidget);
    expect(find.bySemanticsLabel(l10n.pageNext), findsOneWidget);
    expect(find.bySemanticsLabel(l10n.zoomIn), findsOneWidget);
    expect(find.bySemanticsLabel(l10n.zoomOut), findsOneWidget);
    for (final key in [
      'viewer-previous',
      'viewer-next',
      'viewer-zoom-in',
      'viewer-zoom-out',
    ]) {
      final size = tester.getSize(find.byKey(ValueKey(key)));
      expect(size.width, greaterThanOrEqualTo(56), reason: key);
      expect(size.height, greaterThanOrEqualTo(56), reason: key);
    }
    // First page, not zoomed: nothing to go back to, nothing to zoom out of.
    expect(_button(tester, 'viewer-previous').onPressed, isNull);
    expect(_button(tester, 'viewer-next').onPressed, isNotNull);
    expect(_button(tester, 'viewer-zoom-out').onPressed, isNull);
    expect(_button(tester, 'viewer-zoom-in').onPressed, isNotNull);
  });

  testWidgets('the + and − buttons zoom in steps and stop at the limits', (
    tester,
  ) async {
    await _open(tester, _bimBoth);

    await tester.tap(find.byKey(const ValueKey('viewer-zoom-in')));
    await tester.pumpAndSettle();
    expect(_scale(tester), closeTo(1.6, 0.01));
    expect(_button(tester, 'viewer-zoom-out').onPressed, isNotNull);

    // Keep pressing: it stops at the maximum and the button switches off.
    for (var i = 0; i < 8; i++) {
      final button = _button(tester, 'viewer-zoom-in');
      if (button.onPressed == null) break;
      await tester.tap(find.byKey(const ValueKey('viewer-zoom-in')));
      await tester.pumpAndSettle();
    }
    expect(_button(tester, 'viewer-zoom-in').onPressed, isNull);
    expect(_scale(tester), greaterThanOrEqualTo(4));

    for (var i = 0; i < 8; i++) {
      if (_button(tester, 'viewer-zoom-out').onPressed == null) break;
      await tester.tap(find.byKey(const ValueKey('viewer-zoom-out')));
      await tester.pumpAndSettle();
    }
    expect(_scale(tester), closeTo(1, 0.001));
    expect(_button(tester, 'viewer-zoom-out').onPressed, isNull);
  });

  testWidgets('double tap zooms in, double tap again fits the page', (
    tester,
  ) async {
    await _open(tester, _bimBoth);
    final page = find.byKey(const ValueKey('page-0'));
    final at = tester.getCenter(page) + const Offset(40, -60);

    await tester.tapAt(at);
    await tester.pump(const Duration(milliseconds: 60));
    await tester.tapAt(at);
    await tester.pumpAndSettle();
    expect(_scale(tester), closeTo(2.5, 0.01));

    await tester.tapAt(at);
    await tester.pump(const Duration(milliseconds: 60));
    await tester.tapAt(at);
    await tester.pumpAndSettle();
    expect(_scale(tester), closeTo(1, 0.001));
  });

  testWidgets('two fingers zoom the page and never turn it', (tester) async {
    await _open(tester, _bimBoth);
    final center = tester.getCenter(find.byKey(const ValueKey('page-0')));

    final a = await tester.startGesture(center - const Offset(30, 0));
    final b = await tester.startGesture(center + const Offset(30, 0));
    await tester.pump();
    for (var i = 1; i <= 8; i++) {
      await a.moveBy(const Offset(-15, 0));
      await b.moveBy(const Offset(15, 0));
      await tester.pump(const Duration(milliseconds: 16));
    }
    await a.up();
    await b.up();
    await tester.pumpAndSettle();

    expect(_scale(tester), greaterThan(1.5));
    expect(_indicator(tester), '1 / 4');
  });

  testWidgets('swiping turns the page only while the page is not zoomed', (
    tester,
  ) async {
    await _open(tester, _bimBoth);
    final page = find.byKey(const ValueKey('page-0'));

    // Zoomed: a swipe moves around inside the page, the page stays.
    await tester.tap(find.byKey(const ValueKey('viewer-zoom-in')));
    await tester.pumpAndSettle();
    for (var i = 0; i < 3; i++) {
      await tester.drag(page, const Offset(-300, 0));
      await tester.pumpAndSettle();
    }
    expect(_indicator(tester), '1 / 4');
    expect(_scale(tester), closeTo(1.6, 0.01));

    // Not zoomed: the same swipe turns the page.
    await tester.tap(find.byKey(const ValueKey('viewer-zoom-out')));
    await tester.pumpAndSettle();
    await tester.drag(page, const Offset(-300, 0));
    await tester.pumpAndSettle();
    expect(_indicator(tester), '2 / 4');
  });

  testWidgets('arrows turn pages and a new page always starts fitted', (
    tester,
  ) async {
    await _open(tester, _bimBoth);

    await tester.tap(find.byKey(const ValueKey('viewer-zoom-in')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('viewer-next')));
    await tester.pumpAndSettle();
    expect(_indicator(tester), '2 / 4');
    expect(_button(tester, 'viewer-zoom-out').onPressed, isNull);
    expect(_button(tester, 'viewer-previous').onPressed, isNotNull);

    await tester.tap(find.byKey(const ValueKey('viewer-next')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('viewer-next')));
    await tester.pumpAndSettle();
    expect(_indicator(tester), '4 / 4');
    expect(_button(tester, 'viewer-next').onPressed, isNull);

    await tester.tap(find.byKey(const ValueKey('viewer-previous')));
    await tester.pumpAndSettle();
    expect(_indicator(tester), '3 / 4');
  });

  testWidgets('a page that cannot be loaded says so and offers a retry', (
    tester,
  ) async {
    await _open(tester, _bimBoth, imagesFail: true);
    await tester.pump();
    final l10n = l10nOf(tester);

    expect(find.text(l10n.pageErrorTitle), findsOneWidget);
    expect(find.widgetWithText(AppButton, l10n.retry), findsOneWidget);
    // The controls stay usable: the next page may well be cached.
    expect(_button(tester, 'viewer-next').onPressed, isNotNull);
    expect(_button(tester, 'viewer-zoom-in').onPressed, isNull);
  });

  testWidgets('pages missing from the bundle show the same calm state', (
    tester,
  ) async {
    await _open(tester, _sok);
    await tester.pumpAndSettle();
    expect(find.text(l10nOf(tester).pageErrorTitle), findsOneWidget);
    expect(_indicator(tester), '1 / 4');
  });

  testWidgets('a brochure with pages and products has two big tabs', (
    tester,
  ) async {
    await _open(tester, _bimBoth);
    final l10n = l10nOf(tester);

    expect(find.byType(ModeTabs), findsOneWidget);
    expect(find.byType(ProductCard), findsNothing);
    for (final key in ['tab-brochure', 'tab-products']) {
      expect(
        tester.getSize(find.byKey(ValueKey(key))).height,
        greaterThanOrEqualTo(56),
      );
    }

    await tester.tap(find.text(l10n.tabProducts));
    await tester.pumpAndSettle();
    expect(find.byType(ProductCard), findsWidgets);
    expect(find.text('Elektrikli Süpürge 2200 W'), findsOneWidget);
    expect(find.text('1.249,90 ₺'), findsOneWidget);

    // "Sayfada göster" leads back to the pages.
    await tester.tap(find.text(l10n.showOnPage).first);
    await tester.pumpAndSettle();
    expect(find.byType(ViewerControls).hitTestable(), findsOneWidget);
    expect(_indicator(tester), '1 / 4');
  });

  testWidgets('a products-only brochure opens straight on the list', (
    tester,
  ) async {
    await _open(tester, _migros);
    await tester.pumpAndSettle();
    expect(find.byType(ModeTabs), findsNothing);
    expect(find.byType(ViewerControls), findsNothing);
    expect(find.byType(ProductCard), findsWidgets);
    expect(find.text('149,50 ₺'), findsOneWidget);
  });

  testWidgets('a brochure that no longer exists is explained', (tester) async {
    await _open(tester, 'gone-brochure');
    final l10n = l10nOf(tester);
    expect(find.text(l10n.brochureGoneTitle), findsOneWidget);
    expect(find.text(l10n.back), findsOneWidget);
    expect(find.byType(StateView), findsOneWidget);
  });

  for (final scale in [1.0, 2.0]) {
    for (final size in [phoneSize, const Size(320, 640)]) {
      testWidgets('viewer and product list do not overflow '
          '(font scale $scale, ${size.width.toInt()} dp wide)', (tester) async {
        await _open(tester, _bimBoth, textScale: scale, size: size);
        expect(tester.takeException(), isNull);
        expect(find.byType(ZoomablePage), findsOneWidget);

        await tester.tap(find.byKey(const ValueKey('tab-products')));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        await tester.drag(find.byType(ListView), const Offset(0, -2500));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
      });
    }
  }

  testWidgets('with reduced motion the zoom jumps instead of animating', (
    tester,
  ) async {
    await _open(tester, _bimBoth, reduceMotion: true);
    await tester.tap(find.byKey(const ValueKey('viewer-zoom-in')));
    await tester.pump();
    expect(_scale(tester), closeTo(1.6, 0.01));
  });
}
