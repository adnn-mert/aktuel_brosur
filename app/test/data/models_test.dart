import 'dart:convert';

import 'package:aktuel_brosur/data/data.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers.dart';

Map<String, dynamic> _copy(Map<String, dynamic> json) =>
    jsonDecode(jsonEncode(json)) as Map<String, dynamic>;

List<dynamic> _brochures(Map<String, dynamic> json) =>
    json['brochures'] as List<dynamic>;

List<dynamic> _chains(Map<String, dynamic> json) =>
    json['chains'] as List<dynamic>;

void main() {
  group('Catalog', () {
    test('parses the bundled sample catalog', () {
      final catalog = sampleCatalog();

      expect(catalog.schemaVersion, 1);
      expect(catalog.minAppVersion, 1);
      expect(catalog.generatedAt, DateTime.utc(2026, 11, 13, 9, 0, 12));
      expect(catalog.generatedAt.isUtc, isTrue);
      expect(catalog.skippedCount, 0);
      expect(catalog.chains.map((c) => c.id), [
        'bim',
        'a101',
        'sok',
        'migros',
        'watsons',
        'carrefoursa',
        'gratis',
      ]);
      expect(catalog.brochures, hasLength(9));

      final bim = catalog.chainById('bim')!;
      expect(bim.name, 'BİM');
      expect(bim.kind, ChainKind.scraped);
      expect(bim.brandColor, 0xFFE30613);
      expect(bim.lastOkAt, DateTime.utc(2026, 11, 13, 8, 58, 41));

      final a101 = catalog.chainById('a101')!;
      expect(a101.isWebView, isTrue);
      expect(a101.webUrl, 'https://www.a101.com.tr/afisler');
      expect(catalog.brochuresOf('a101'), isEmpty);

      expect(catalog.chainById('watsons')!.isStale, isTrue);
      expect(catalog.chainById('carrefoursa')!.lastOkAt, isNull);

      final sok = catalog.brochureById('sok-2026-11-11-haftanin-firsatlari')!;
      expect(sok.kind, BrochureKind.pages);
      expect(sok.validFrom, DateTime(2026, 11, 11));
      expect(sok.validTo, DateTime(2026, 11, 17));
      expect(sok.pages, hasLength(4));
      expect(
        sok.pages.first,
        const MediaImage(
          url: 'media/sok/sok-2026-11-11-haftanin-firsatlari/p01.webp',
          width: 1600,
          height: 2263,
        ),
      );
      expect(sok.hasPages, isTrue);
      expect(sok.hasProducts, isFalse);

      final bimFriday = catalog.brochureById('bim-2026-11-13-cuma')!;
      expect(bimFriday.kind, BrochureKind.both);
      expect(bimFriday.cover!.width, isNull);
      expect(bimFriday.cover!.aspectRatio, isNull);
      expect(bimFriday.productsUrl, 'products/bim-2026-11-13-cuma.json');
      expect(bimFriday.hasPages && bimFriday.hasProducts, isTrue);

      final migros = catalog.brochureById('migros-910')!;
      expect(migros.kind, BrochureKind.products);
      expect(migros.pages, isEmpty);
      expect(migros.hasPages, isFalse);
      expect(migros.thumbnail, migros.cover);
    });

    test('equal input gives equal catalogs', () {
      expect(sampleCatalog(), sampleCatalog());
      expect(sampleCatalog().hashCode, sampleCatalog().hashCode);
    });

    test('ignores unknown fields everywhere', () {
      final json = _copy(sampleJson('catalog.json'));
      json['future_root_field'] = {'x': 1};
      for (final c in _chains(json)) {
        (c as Map<String, dynamic>)['future'] = [1, 2];
      }
      for (final b in _brochures(json)) {
        final map = b as Map<String, dynamic>;
        map['future'] = 'yes';
        for (final p in map['pages'] as List<dynamic>) {
          (p as Map<String, dynamic>)['dpi'] = 300;
        }
      }
      expect(Catalog.fromJson(json), sampleCatalog());
    });

    test('skips a brochure with an unknown kind and counts it', () {
      final json = _copy(sampleJson('catalog.json'));
      (_brochures(json).first as Map<String, dynamic>)['kind'] = 'video';

      final catalog = Catalog.fromJson(json);

      expect(catalog.brochures, hasLength(8));
      expect(catalog.brochureById('bim-2026-11-13-cuma'), isNull);
      expect(catalog.skippedBrochureCount, 1);
      expect(catalog.skippedCount, 1);
    });

    test('skips a chain with an unknown kind together with its brochures', () {
      final json = _copy(sampleJson('catalog.json'));
      (_chains(json).first as Map<String, dynamic>)['kind'] = 'app_only';

      final catalog = Catalog.fromJson(json);

      expect(catalog.chainById('bim'), isNull);
      expect(catalog.brochuresOf('bim'), isEmpty);
      expect(catalog.skippedChainCount, 1);
      // The three BİM brochures lost their chain.
      expect(catalog.skippedBrochureCount, 3);
      expect(catalog.skippedCount, 4);
      expect(catalog.chains, hasLength(6));
    });

    test('an unknown status does not drop the chain', () {
      final json = _copy(sampleJson('catalog.json'));
      (_chains(json).first as Map<String, dynamic>)['status'] = 'degraded';
      final catalog = Catalog.fromJson(json);
      expect(catalog.chainById('bim')!.status, ChainStatus.ok);
      expect(catalog.skippedCount, 0);
    });

    test('a broken record is skipped, the rest survives', () {
      final json = _copy(sampleJson('catalog.json'));
      final brochures = _brochures(json);
      (brochures[0] as Map<String, dynamic>).remove('title');
      (brochures[1] as Map<String, dynamic>)['valid_from'] = '2026-02-30';
      (brochures[2] as Map<String, dynamic>)['pages'] = 'not a list';
      brochures.add(42);
      (_chains(json)[1] as Map<String, dynamic>)['id'] = 'Bad Id!';
      (_chains(json)[2] as Map<String, dynamic>)['brand_color'] = 'red';

      final catalog = Catalog.fromJson(json);

      expect(catalog.chainById('a101'), isNull);
      expect(catalog.skippedChainCount, 1);
      expect(catalog.skippedBrochureCount, 4);
      expect(catalog.brochures, hasLength(9 - 3));
      // A bad colour only loses the colour.
      expect(catalog.chainById('sok')!.brandColor, isNull);
    });

    test('rejects self-contradictory brochures', () {
      final json = _copy(sampleJson('catalog.json'));
      final brochures = _brochures(json);
      // Starts after it ends.
      (brochures[0] as Map<String, dynamic>)['valid_from'] = '2026-11-20';
      // Page brochure without pages.
      (brochures[1] as Map<String, dynamic>)['pages'] = <dynamic>[];

      final catalog = Catalog.fromJson(json);

      expect(catalog.skippedBrochureCount, 2);
    });

    test('a broken root throws CatalogFormatException', () {
      final good = sampleJson('catalog.json');
      final cases = <String, Object?>{
        'array root': <dynamic>[],
        'missing chains': _copy(good)..remove('chains'),
        'brochures not a list': _copy(good)..['brochures'] = {},
        'bad generated_at': _copy(good)..['generated_at'] = 'yesterday',
        'schema_version string': _copy(good)..['schema_version'] = '1',
        'min_app_version zero': _copy(good)..['min_app_version'] = 0,
      };
      for (final entry in cases.entries) {
        expect(
          () => Catalog.fromJson(entry.value),
          throwsA(isA<CatalogFormatException>()),
          reason: entry.key,
        );
      }
      expect(
        () => Catalog.parse('{"schema_version": 1,'),
        throwsA(isA<CatalogFormatException>()),
      );
    });
  });

  group('ProductFile', () {
    test('parses the sample product files', () {
      final migros = ProductFile.parse(sampleText('products/migros-910.json'));
      expect(migros.brochureId, 'migros-910');
      expect(migros.currency, 'TRY');
      expect(migros.products, hasLength(7));
      expect(migros.skippedCount, 0);

      final first = migros.products.first;
      expect(first.name, 'Banada Kakaolu Fındık Kreması');
      expect(first.brand, 'Torku');
      expect(first.quantityText, '700 g');
      expect(first.price, const Money(14950));
      expect(first.oldPrice, const Money(18950));
      expect(first.discountPercent, 21);
      expect(first.price.format(), '149,50 ₺');

      final kiyma = migros.products[2];
      expect(kiyma.brand, isNull);
      expect(kiyma.image, isNull);

      final bim = ProductFile.parse(
        sampleText('products/bim-2026-11-13-cuma.json'),
      );
      final catalog = sampleCatalog();
      expect(
        bim.products,
        hasLength(catalog.brochureById('bim-2026-11-13-cuma')!.productCount),
      );
      expect(bim.products.first.discountPercent, isNull);
    });

    test('skips broken products and ignores unknown fields', () {
      final json = _copy(sampleJson('products/migros-910.json'));
      final products = json['products'] as List<dynamic>;
      (products[0] as Map<String, dynamic>)['price_minor'] = '149,50';
      (products[1] as Map<String, dynamic>).remove('name');
      (products[2] as Map<String, dynamic>)['barcode'] = '869000000';
      json['extra'] = true;

      final file = ProductFile.fromJson(json);

      expect(file.products, hasLength(5));
      expect(file.skippedCount, 2);
    });

    test('a broken root throws CatalogFormatException', () {
      expect(
        () => ProductFile.parse('not json'),
        throwsA(isA<CatalogFormatException>()),
      );
      expect(
        () => ProductFile.fromJson({'schema_version': 1, 'products': []}),
        throwsA(isA<CatalogFormatException>()),
      );
    });

    test('equality', () {
      final a = ProductFile.parse(sampleText('products/migros-910.json'));
      final b = ProductFile.parse(sampleText('products/migros-910.json'));
      expect(a, b);
      expect(a.hashCode, b.hashCode);
    });
  });
}
