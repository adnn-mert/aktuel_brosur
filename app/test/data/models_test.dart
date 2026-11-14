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

    group('member price', () {
      // A valid shelf-priced product plus whatever member fields a case sets.
      Product parse(Map<String, Object?> member) => Product.fromJson({
        'name': 'Tam Buğday Ekmeği 400 g',
        'price_minor': 9995,
        'old_price_minor': 11995,
        ...member,
      });

      test('both fields set', () {
        final p = parse({
          'member_price_minor': 7795,
          'member_price_label': 'Money ile',
        });
        expect(p.hasMemberPrice, isTrue);
        expect(p.memberPrice, const Money(7795));
        expect(p.memberPriceLabel, 'Money ile');
        // The shelf price and its discount are untouched.
        expect(p.price, const Money(9995));
        expect(p.discountPercent, 17);
      });

      test('the label is trimmed', () {
        final p = parse({
          'member_price_minor': 7795,
          'member_price_label': '  Money ile ',
        });
        expect(p.memberPriceLabel, 'Money ile');
      });

      final dropped = <(String, Map<String, Object?>)>[
        ('fields absent', {}),
        ('both null', {'member_price_minor': null, 'member_price_label': null}),
        ('only the price', {'member_price_minor': 7795}),
        ('only the label', {'member_price_label': 'Money ile'}),
        ('empty label', {'member_price_minor': 7795, 'member_price_label': ''}),
        (
          'blank label',
          {'member_price_minor': 7795, 'member_price_label': '   '},
        ),
        (
          'equal to the shelf price',
          {'member_price_minor': 9995, 'member_price_label': 'Money ile'},
        ),
        (
          'above the shelf price',
          {'member_price_minor': 12000, 'member_price_label': 'Money ile'},
        ),
        (
          'negative',
          {'member_price_minor': -1, 'member_price_label': 'Money ile'},
        ),
        (
          'price as text',
          {'member_price_minor': '77,95', 'member_price_label': 'Money ile'},
        ),
        (
          'fractional price',
          {'member_price_minor': 77.95, 'member_price_label': 'Money ile'},
        ),
        (
          'label not text',
          {'member_price_minor': 7795, 'member_price_label': 1},
        ),
      ];
      for (final (name, member) in dropped) {
        test('dropped, product kept: $name', () {
          final p = parse(member);
          expect(p.name, 'Tam Buğday Ekmeği 400 g');
          expect(p.price, const Money(9995));
          expect(p.discountPercent, 17);
          expect(p.hasMemberPrice, isFalse);
          expect(p.memberPrice, isNull);
          expect(p.memberPriceLabel, isNull);
        });
      }

      test('a bad member price never makes the file skip the product', () {
        final json = _copy(sampleJson('products/migros-910.json'));
        final products = json['products'] as List<dynamic>;
        (products.last as Map<String, dynamic>)['member_price_minor'] = 'x';
        final file = ProductFile.fromJson(json);
        expect(file.products, hasLength(10));
        expect(file.skippedCount, 0);
        expect(file.products.last.hasMemberPrice, isFalse);
      });

      test('the constructor keeps the pair together', () {
        const lonePrice = Product(
          name: 'x',
          price: Money(100),
          memberPrice: Money(90),
        );
        const loneLabel = Product(
          name: 'x',
          price: Money(100),
          memberPriceLabel: 'Money ile',
        );
        expect(lonePrice.hasMemberPrice, isFalse);
        expect(loneLabel.memberPriceLabel, isNull);
      });

      test('takes part in equality', () {
        final a = parse({
          'member_price_minor': 7795,
          'member_price_label': 'Money ile',
        });
        final b = parse({
          'member_price_minor': 7795,
          'member_price_label': 'Money ile',
        });
        expect(a, b);
        expect(a.hashCode, b.hashCode);
        expect(a, isNot(parse({})));
      });
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
      expect(
        migros.products,
        hasLength(sampleCatalog().brochureById('migros-910')!.productCount),
      );
      expect(migros.products, hasLength(10));
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
      expect(kiyma.hasMemberPrice, isFalse);
      expect(kiyma.memberPrice, isNull);
      expect(kiyma.memberPriceLabel, isNull);

      // Money card prices, as Migros printed them.
      final members = {
        for (final p in migros.products.where((p) => p.hasMemberPrice))
          p.name: (
            p.price.format(),
            p.memberPrice!.format(),
            p.memberPriceLabel,
            p.quantityText,
          ),
      };
      expect(members, {
        'Tam Buğday Ekmeği 400 g': ('99,95 ₺', '77,95 ₺', 'Money ile', null),
        "Natural Kişisel Bakım Havlusu 100'lü": (
          '159,95 ₺',
          '99,95 ₺',
          'Money ile',
          null,
        ),
        'Siirt Fıstığı Tuzlu Kavrulmuş': (
          '1.799,00 ₺',
          '1.499,90 ₺',
          'Money ile',
          'kg fiyatı',
        ),
      });

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

      expect(file.products, hasLength(8));
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
