import 'package:aktuel_brosur/data/data.dart';
import 'package:aktuel_brosur/design/theme.dart';
import 'package:aktuel_brosur/design/widgets/app_buttons.dart';
import 'package:aktuel_brosur/design/widgets/app_scaffold.dart';
import 'package:aktuel_brosur/design/widgets/chain_mark.dart';
import 'package:aktuel_brosur/design/widgets/feedback.dart';
import 'package:aktuel_brosur/features/app/app.dart';
import 'package:aktuel_brosur/features/chain/brochure_card.dart';
import 'package:aktuel_brosur/features/chain/chain_screen.dart';
import 'package:aktuel_brosur/features/home/chain_card.dart';
import 'package:aktuel_brosur/features/home/home_screen.dart';
import 'package:aktuel_brosur/features/products/product_card.dart';
import 'package:aktuel_brosur/features/splash/splash_screen.dart';
import 'package:aktuel_brosur/features/web/web_catalog_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers.dart';
import 'support.dart';

void main() {
  group('market screen', () {
    testWidgets('groups brochures under the three everyday headings', (
      tester,
    ) async {
      final image = await makeTestImage(tester);
      await pumpUi(
        tester,
        const ChainScreen(chainId: 'bim'),
        overrides: uiOverrides(image: image),
        size: const Size(411, 2400),
      );
      final l10n = l10nOf(tester);

      expect(find.text(l10n.sectionCurrent), findsOneWidget);
      expect(find.text(l10n.sectionUpcoming), findsOneWidget);
      expect(find.text(l10n.sectionPast), findsOneWidget);
      expect(find.byType(BrochureCard), findsNWidgets(3));
      expect(find.text(l10n.back), findsOneWidget);

      // Dates in everyday words; the title does not repeat the date.
      expect(find.text('13 Kasım Cuma'), findsOneWidget);
      expect(find.text('Aktüel Ürünler'), findsNWidgets(3));
      expect(find.text('4 sayfa · 14 ürün'), findsOneWidget);
      expect(find.text('3 Kasım Salı'), findsOneWidget);

      // Headings come in reading order.
      final current = tester.getTopLeft(find.text(l10n.sectionCurrent)).dy;
      final upcoming = tester.getTopLeft(find.text(l10n.sectionUpcoming)).dy;
      final past = tester.getTopLeft(find.text(l10n.sectionPast)).dy;
      expect(current < upcoming && upcoming < past, isTrue);

      // The brochure first seen today is marked.
      expect(
        find.descendant(
          of: find.byKey(const ValueKey('brochure-bim-2026-11-18-carsamba')),
          matching: find.text(l10n.badgeNew),
        ),
        findsOneWidget,
      );
    });

    testWidgets('a market whose data is outdated says so calmly', (
      tester,
    ) async {
      // Give Watsons a second brochure so its market screen is reachable.
      await pumpUi(
        tester,
        const ChainScreen(chainId: 'watsons'),
        overrides: uiOverrides(),
      );
      final l10n = l10nOf(tester);
      expect(
        find.widgetWithText(NoticeStrip, l10n.chainStaleNotice),
        findsOneWidget,
      );
      expect(find.textContaining('12 Kasım'), findsOneWidget);
    });

    testWidgets('an empty market explains and offers the market site', (
      tester,
    ) async {
      final json = sampleJson('catalog.json');
      (json['brochures'] as List).removeWhere(
        (b) => (b as Map)['chain_id'] == 'migros',
      );
      await pumpUi(
        tester,
        const ChainScreen(chainId: 'migros'),
        overrides: uiOverrides(
          repository: FakeRepository(catalog: Catalog.fromJson(json)),
        ),
      );
      final l10n = l10nOf(tester);
      expect(find.text(l10n.emptyChainTitle), findsOneWidget);
      expect(find.text(l10n.emptyChainMessage('Migros')), findsOneWidget);
      expect(
        find.widgetWithText(AppButton, l10n.openChainWebsite),
        findsOneWidget,
      );
    });

    for (final scale in [1.0, 2.0]) {
      testWidgets('no overflow at font scale $scale', (tester) async {
        final image = await makeTestImage(tester);
        await pumpUi(
          tester,
          const ChainScreen(chainId: 'bim'),
          overrides: uiOverrides(image: image),
          textScale: scale,
          brightness: Brightness.dark,
        );
        expect(tester.takeException(), isNull);
        await tester.drag(find.byType(ListView), const Offset(0, -3000));
        await tester.pump();
        expect(tester.takeException(), isNull);
      });
    }
  });

  group('market mark', () {
    Chain sample(String id) => sampleCatalog().chainById(id)!;

    testWidgets('a market with a bundled logo shows the logo', (tester) async {
      await pumpUi(tester, Scaffold(body: ChainMark(chain: sample('bim'))));
      expect(find.byType(Image), findsOneWidget);
      expect(find.bySemanticsLabel('BİM'), findsOneWidget);
    });

    testWidgets('a market without a logo shows its name on its colour', (
      tester,
    ) async {
      await pumpUi(tester, Scaffold(body: ChainMark(chain: sample('a101'))));
      expect(find.byType(Image), findsNothing);
      expect(find.text('A101'), findsOneWidget);
      final plate = tester.widget<Container>(find.byType(Container).first);
      expect(
        (plate.decoration! as BoxDecoration).color,
        const Color(0xFF00A0E3),
      );
    });

    testWidgets('an unknown future market still gets a readable name card', (
      tester,
    ) async {
      await pumpUi(
        tester,
        Scaffold(
          body: SizedBox(
            width: 150,
            child: ChainMark(
              chain: chain('tkkoop', name: 'Tarım Kredi Kooperatif'),
            ),
          ),
        ),
      );
      expect(find.text('Tarım Kredi Kooperatif'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });

  group('product card', () {
    const product = Product(
      name: 'Süzme Peynir',
      brand: 'Sütaş',
      quantityText: '500 g',
      price: Money(11990),
      oldPrice: Money(14990),
    );

    testWidgets('shows name, brand, amount, price, old price and discount', (
      tester,
    ) async {
      await pumpUi(
        tester,
        const Scaffold(body: ProductCard(product: product)),
        overrides: uiOverrides(),
      );
      final l10n = l10nOf(tester);
      expect(find.text('Süzme Peynir'), findsOneWidget);
      expect(find.text('Sütaş · 500 g'), findsOneWidget);
      expect(find.text('119,90 ₺'), findsOneWidget);
      expect(find.text('149,90 ₺'), findsOneWidget);
      expect(find.text(l10n.discountPercent(20)), findsOneWidget);
      expect(find.text(l10n.showOnPage), findsNothing);

      final old = tester.widget<Text>(find.text('149,90 ₺'));
      expect(old.style!.decoration, TextDecoration.lineThrough);
      final price = tester.widget<Text>(find.text('119,90 ₺'));
      expect(price.style!.fontSize, greaterThan(old.style!.fontSize!));
    });

    testWidgets('"Sayfada göster" appears only when a page is known', (
      tester,
    ) async {
      var shown = 0;
      await pumpUi(
        tester,
        Scaffold(
          body: ProductCard(product: product, onShowPage: () => shown++),
        ),
        overrides: uiOverrides(),
        textScale: 2,
      );
      final button = find.widgetWithText(AppButton, l10nOf(tester).showOnPage);
      expect(tester.getSize(button).height, greaterThanOrEqualTo(56));
      await tester.tap(button);
      expect(shown, 1);
      expect(tester.takeException(), isNull);
    });
  });

  group('shared pieces', () {
    testWidgets('"Geri" is a labelled, 56 dp button on every top bar', (
      tester,
    ) async {
      await pumpUi(
        tester,
        const AppScaffold(
          topBar: AppTopBar(title: 'CarrefourSA', subtitle: '13–19 Kasım'),
          body: SizedBox(),
        ),
        textScale: 2,
      );
      final back = find.byType(BackButtonPill);
      expect(find.text(l10nOf(tester).back), findsOneWidget);
      expect(tester.getSize(back).height, greaterThanOrEqualTo(56));
      expect(find.text('CarrefourSA'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('web page failure: plain message, retry and browser buttons', (
      tester,
    ) async {
      var retried = 0;
      var opened = 0;
      await pumpUi(
        tester,
        Scaffold(
          body: WebCatalogError(
            chainName: 'Gratis',
            onRetry: () => retried++,
            onOpenInBrowser: () => opened++,
          ),
        ),
        textScale: 2,
      );
      final l10n = l10nOf(tester);
      expect(find.text(l10n.webErrorTitle), findsOneWidget);
      expect(find.text(l10n.webErrorMessage('Gratis')), findsOneWidget);
      await tester.ensureVisible(find.text(l10n.retry));
      await tester.tap(find.text(l10n.retry));
      await tester.ensureVisible(find.text(l10n.openInBrowser));
      await tester.tap(find.text(l10n.openInBrowser));
      expect((retried, opened), (1, 1));
      expect(tester.takeException(), isNull);
    });

    testWidgets('web bar hides "Sitede geri" until there is a page behind', (
      tester,
    ) async {
      Widget bar({required bool canGoBack}) => Scaffold(
        body: WebCatalogBar(
          canGoBack: canGoBack,
          onBackInSite: () {},
          onOpenInBrowser: () {},
        ),
      );
      await pumpUi(tester, bar(canGoBack: false));
      final l10n = l10nOf(tester);
      expect(find.text(l10n.webBack), findsNothing);
      expect(find.text(l10n.openInBrowser), findsOneWidget);

      await pumpUi(tester, bar(canGoBack: true));
      expect(find.text(l10n.webBack), findsOneWidget);
    });

    testWidgets('the favourite star changes shape, not only colour', (
      tester,
    ) async {
      Widget star({required bool on}) => Scaffold(
        body: FavoriteStar(isFavorite: on, label: 'x', onPressed: () {}),
      );
      await pumpUi(tester, star(on: false));
      expect(find.byIcon(Icons.star_rounded), findsNothing);
      expect(find.byIcon(Icons.star_outline_rounded), findsOneWidget);
      await pumpUi(tester, star(on: true));
      expect(find.byIcon(Icons.star_rounded), findsOneWidget);
      expect(find.byIcon(Icons.star_outline_rounded), findsOneWidget);
    });

    testWidgets('status lines of a market card', (tester) async {
      await pumpUi(tester, const Scaffold(body: SizedBox()));
      final l10n = l10nOf(tester);
      ChainSummary summary(String id) => chainSummary(
        sampleCatalog().chainById(id)!,
        sampleCatalog().brochures,
        sampleToday,
      );
      expect(chainStatusLines(l10n, summary('bim')), (
        first: 'Bu hafta',
        second: '1 broşür',
      ));
      expect(chainStatusLines(l10n, summary('a101')), (
        first: 'Marketin sitesi',
        second: null,
      ));
    });
  });

  group('splash', () {
    testWidgets('plays, then reveals the home screen with data loaded', (
      tester,
    ) async {
      tester.view.physicalSize = phoneSize;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(
        ProviderScope(overrides: uiOverrides(), child: const CarsiPazarApp()),
      );
      await tester.pump();
      expect(find.byType(SplashScreen), findsOneWidget);
      // The home screen is already being built underneath.
      expect(find.byType(HomeScreen), findsOneWidget);

      await tester.pump(const Duration(milliseconds: 1600));
      await tester.pump(const Duration(milliseconds: 1000));
      expect(find.byType(SplashScreen), findsOneWidget);
      await tester.pump(const Duration(milliseconds: 1500));
      await tester.pump(const Duration(milliseconds: 500));
      await tester.pump(const Duration(milliseconds: 500));
      expect(find.byType(SplashScreen), findsNothing);
      expect(find.byType(ChainCard), findsWidgets);
      expect(tester.takeException(), isNull);
    });

    testWidgets('with reduced motion it shows a still logo briefly', (
      tester,
    ) async {
      var finished = false;
      await pumpUi(
        tester,
        SplashScreen(onFinished: () => finished = true),
        reduceMotion: true,
      );
      final context = tester.element(find.byType(SplashScreen));
      expect(context.reduceMotion, isTrue);
      expect(find.text('Çarşı Pazar'), findsOneWidget);
      expect(finished, isFalse);
      await tester.pump(const Duration(seconds: 1));
      expect(finished, isTrue);
    });
  });
}
