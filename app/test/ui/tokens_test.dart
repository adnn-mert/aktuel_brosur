import 'package:aktuel_brosur/data/data.dart';
import 'package:aktuel_brosur/design/chain_logos.dart';
import 'package:aktuel_brosur/design/tokens.dart';
import 'package:aktuel_brosur/design/typography.dart';
import 'package:flutter/material.dart';
import 'package:aktuel_brosur/design/widgets/chain_mark.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers.dart';
import 'support.dart';

void main() {
  for (final (name, c) in [
    ('light', AppColors.light),
    ('dark', AppColors.dark),
  ]) {
    group('$name palette contrast', () {
      void atLeast(String what, Color a, Color b, double ratio) {
        test(what, () {
          expect(
            contrastRatio(a, b),
            greaterThanOrEqualTo(ratio),
            reason: '$what is ${contrastRatio(a, b).toStringAsFixed(2)}:1',
          );
        });
      }

      // Body text: well above WCAG AA (4.5), at AAA level.
      atLeast('ink on paper', c.ink, c.paper, 7);
      atLeast('ink on surface', c.ink, c.surface, 7);
      atLeast('soft ink on paper', c.inkSoft, c.paper, 7);
      atLeast('soft ink on surface', c.inkSoft, c.surface, 7);
      atLeast('soft ink on sunken surface', c.inkSoft, c.surfaceSunken, 4.5);
      // Buttons and badges.
      atLeast('primary button label', c.onPrimary, c.primary, 4.5);
      atLeast('tonal button label', c.onPrimarySoft, c.primarySoft, 7);
      atLeast('"Yeni" badge label', c.onFresh, c.fresh, 4.5);
      atLeast('notice text', c.onNotice, c.notice, 7);
      // Shapes that must be visible without relying on colour.
      atLeast('control outline on paper', c.lineStrong, c.paper, 3);
      atLeast('primary shape on paper', c.primary, c.paper, 3);
      atLeast('star outline on surface', c.starOutline, c.surface, 3);
    });
  }

  test('text on any brand colour stays readable', () {
    const brands = [
      Color(0xFFE30613), // BİM red
      Color(0xFF00A0E3), // A101 cyan
      Color(0xFFFFD100), // Şok yellow
      Color(0xFFFF8300), // Migros orange
      Color(0xFF00A6A6), // Watsons teal
      Color(0xFF1E5BC6), // CarrefourSA blue
      Color(0xFFE5007D), // Gratis pink
      Color(0xFFFFFFFF),
      Color(0xFF000000),
      Color(0xFF777777),
    ];
    for (final brand in brands) {
      final text = AppColors.light.onBrand(brand);
      expect(
        contrastRatio(text, brand),
        greaterThanOrEqualTo(4.5),
        reason: brand.toString(),
      );
    }
  });

  group('name-card colours of chains without a catalog colour', () {
    test('cover the new chains and keep the name readable', () {
      expect(
        chainPlateColors.keys,
        containsAll(['hakmar', 'bonveno', 'metro', 'rossmann', 'tkkoop']),
      );
      for (final MapEntry(key: id, value: plate) in chainPlateColors.entries) {
        for (final c in [AppColors.light, AppColors.dark]) {
          expect(
            contrastRatio(c.onBrand(plate), plate),
            greaterThanOrEqualTo(4.5),
            reason: id,
          );
        }
        // No bundled logo: these are name cards, not logo plates.
        expect(chainLogos.containsKey(id), isFalse, reason: id);
      }
      // Every plate is its own colour.
      expect(chainPlateColors.values.toSet().length, chainPlateColors.length);
    });

    Color plateOf(WidgetTester tester) =>
        (tester.widget<Container>(find.byType(Container)).decoration!
                as BoxDecoration)
            .color!;

    testWidgets('a chain without a colour gets its plate colour', (
      tester,
    ) async {
      await pumpUi(
        tester,
        Scaffold(
          body: ChainMark(chain: chain('tkkoop', name: 'Tarım Kredi')),
        ),
      );
      expect(plateOf(tester), chainPlateColors['tkkoop']);
      expect(find.text('Tarım Kredi'), findsOneWidget);
    });

    testWidgets('a colour from the catalog wins over the plate colour', (
      tester,
    ) async {
      const fromCatalog = Chain(
        id: 'hakmar',
        name: 'Hakmar',
        kind: ChainKind.scraped,
        webUrl: 'https://example.com',
        status: ChainStatus.ok,
        lastOkAt: null,
        sortOrder: 0,
        brandColor: 0xFF123456,
      );
      await pumpUi(tester, const Scaffold(body: ChainMark(chain: fromCatalog)));
      expect(plateOf(tester), const Color(0xFF123456));
    });

    testWidgets('an unknown chain without a colour keeps the calm plate', (
      tester,
    ) async {
      await pumpUi(
        tester,
        Scaffold(
          body: ChainMark(chain: chain('yeni', name: 'Yeni Market')),
        ),
      );
      expect(plateOf(tester), AppColors.light.primarySoft);
    });
  });

  test('no text style is smaller than 18 sp', () {
    const styles = {
      'wordmark': AppType.wordmark,
      'headline': AppType.headline,
      'section': AppType.section,
      'title': AppType.title,
      'body': AppType.body,
      'bodyStrong': AppType.bodyStrong,
      'label': AppType.label,
      'badge': AppType.badge,
      'chainName': AppType.chainName,
      'price': AppType.price,
      'priceOld': AppType.priceOld,
      'pageIndicator': AppType.pageIndicator,
    };
    for (final MapEntry(key: name, value: style) in styles.entries) {
      expect(style.fontSize, greaterThanOrEqualTo(18), reason: name);
      expect(style.fontFamily, isNotNull, reason: name);
    }
  });

  test('touch targets are at least 56 dp', () {
    expect(AppSize.touch, greaterThanOrEqualTo(56));
    expect(AppSize.touchLarge, greaterThanOrEqualTo(AppSize.touch));
  });

  test('pages stay cached for offline reading for at least 30 days', () {
    expect(AppCachePolicy.keepFor.inDays, greaterThanOrEqualTo(30));
  });
}
