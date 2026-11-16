// Products read from brochure pages by OCR (`ocr_products_url`,
// `products_ocr/<id>.json`, `source: "ocr"`): parsing, loading, caching and
// search.
import 'dart:convert';
import 'dart:io';

import 'package:aktuel_brosur/data/data.dart';
import 'package:aktuel_brosur/features/app/navigation.dart' show searchHitPage;
import 'package:flutter/foundation.dart' show listEquals;
import 'package:flutter/services.dart' show rootBundle;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../helpers.dart';

const _sokId = 'sok-2026-11-11-haftanin-firsatlari';
const _base = 'https://example.github.io/aktuel_brosur';

Map<String, dynamic> _copy(Map<String, dynamic> json) =>
    jsonDecode(jsonEncode(json)) as Map<String, dynamic>;

Map<String, dynamic> _brochureJson(Map<String, dynamic> catalog, String id) =>
    (catalog['brochures'] as List<dynamic>)
        .cast<Map<String, dynamic>>()
        .firstWhere((b) => b['id'] == id);

/// A valid product record plus [extra] fields.
Map<String, Object?> _productJson([Map<String, Object?> extra = const {}]) => {
  'name': 'Ayçiçek Yağı',
  'brand': 'Yudum',
  'quantity_text': '5 L',
  'price_minor': 34990,
  'old_price_minor': null,
  'image': null,
  'page_index': 0,
  'source_url': null,
  ...extra,
};

Map<String, Object?> _fileJson(List<Object?> products) => {
  'schema_version': 1,
  'brochure_id': _sokId,
  'currency': 'TRY',
  'products': products,
};

/// A page brochure with an OCR list, built without JSON.
Brochure _ocrBrochure(
  String id, {
  String chainId = 'sok',
  DateTime? from,
  DateTime? to,
  int pageCount = 4,
  String? productsUrl,
  BrochureKind kind = BrochureKind.pages,
}) {
  final base = brochure(id, chainId: chainId, from: from, to: to);
  return Brochure(
    id: id,
    chainId: chainId,
    title: id,
    dateLabel: null,
    validFrom: from,
    validTo: to,
    kind: kind,
    cover: null,
    pages: [
      for (var i = 0; i < pageCount; i++) MediaImage(url: 'media/$id/p$i.webp'),
    ],
    productsUrl: productsUrl,
    productCount: productsUrl == null ? 0 : 1,
    sourceUrl: base.sourceUrl,
    firstSeen: base.firstSeen,
    updatedAt: base.updatedAt,
    ocrProductsUrl: 'products_ocr/$id.json',
  );
}

class _Server {
  final List<http.Response Function()> handlers = [];
  final List<http.Request> requests = [];

  late final http.Client client = MockClient((request) async {
    requests.add(request);
    if (handlers.isEmpty) fail('unexpected request ${request.url}');
    return handlers.removeAt(0)();
  });

  void respond(String body, {int status = 200, String? etag}) => handlers.add(
    () => http.Response.bytes(
      utf8.encode(body),
      status,
      headers: {'etag': ?etag},
    ),
  );

  void notModified() => handlers.add(() => http.Response('', 304));

  void offline() => handlers.add(() => throw const SocketException('offline'));
}

/// Serves products by brochure id and records which brochures were asked for.
class _Repo implements CatalogRepository {
  _Repo(this.files);

  final Map<String, ProductFile> files;
  final List<String> requested = [];

  @override
  Future<CatalogResult> loadCatalog({bool forceRefresh = false}) =>
      throw UnimplementedError();

  @override
  Future<ProductFile> loadProducts(Brochure brochure) async {
    requested.add(brochure.id);
    final file = files[brochure.id];
    if (file == null) throw ProductsUnavailableException(brochure.id);
    return file;
  }

  @override
  Uri resolve(String url) => Uri.parse(url);
}

ProductFile _file(
  String brochureId,
  List<Product> products, {
  ProductSource source = ProductSource.written,
}) => ProductFile(
  schemaVersion: 1,
  brochureId: brochureId,
  currency: 'TRY',
  products: products,
  source: source,
);

Product _ocr(String name, int minor, {int page = 0}) => Product(
  name: name,
  price: Money(minor),
  pageIndex: page,
  source: ProductSource.ocr,
);

Product _written(String name, int minor) =>
    Product(name: name, price: Money(minor));

Catalog _catalog(List<Brochure> brochures) => Catalog(
  schemaVersion: 1,
  generatedAt: DateTime.utc(2026, 11, 13),
  minAppVersion: 1,
  chains: [
    chain('bim', name: 'BİM'),
    chain('sok', name: 'Şok'),
    chain('migros', name: 'Migros'),
  ],
  brochures: brochures,
);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('Brochure.ocrProductsUrl', () {
    test('the sample Şok brochure has an OCR list only', () {
      final sok = sampleCatalog().brochureById(_sokId)!;
      expect(sok.ocrProductsUrl, 'products_ocr/$_sokId.json');
      expect(sok.kind, BrochureKind.pages);
      expect(sok.productsUrl, isNull);
      expect(sok.hasProducts, isFalse);
      expect(sok.hasOcrProducts, isTrue);
      expect(sok.hasProductList, isTrue);
      expect(sok.productListSource, ProductSource.ocr);
    });

    test('brochures without the field are unchanged (older catalogs)', () {
      final catalog = sampleCatalog();
      final bim = catalog.brochureById('bim-2026-11-13-cuma')!;
      expect(bim.ocrProductsUrl, isNull);
      expect(bim.hasOcrProducts, isFalse);
      expect(bim.productListSource, ProductSource.written);
      final migros = catalog.brochureById('migros-910')!;
      expect(migros.productListSource, ProductSource.written);
      final oldSok = catalog.brochureById(
        'sok-2026-11-18-haftanin-firsatlari',
      )!;
      expect(oldSok.hasProductList, isFalse);
      expect(oldSok.productListSource, isNull);
    });

    test('a catalog published before the field parses as before', () {
      final json = _copy(sampleJson('catalog.json'));
      _brochureJson(json, _sokId).remove('ocr_products_url');
      final catalog = Catalog.fromJson(json);
      final sok = catalog.brochureById(_sokId)!;
      expect(catalog.skippedCount, 0);
      expect(sok.hasProductList, isFalse);
      expect(sok, isNot(sampleCatalog().brochureById(_sokId)));
    });

    for (final (name, value) in <(String, Object?)>[
      ('null', null),
      ('a number', 42),
      ('a list', ['products_ocr/x.json']),
      ('empty', ''),
      ('blank', '  '),
      ('absolute https', 'https://evil.example/x.json'),
      ('a scheme', 'file:products_ocr/x.json'),
      ('a leading slash', '/products_ocr/x.json'),
      ('dot-dot', 'products_ocr/../catalog.json'),
      ('whitespace', 'products_ocr/a b.json'),
      ('a backslash', r'products_ocr\x.json'),
    ]) {
      test('a malformed value ($name) drops only the OCR list', () {
        final json = _copy(sampleJson('catalog.json'));
        _brochureJson(json, _sokId)['ocr_products_url'] = value;
        final catalog = Catalog.fromJson(json);
        final sok = catalog.brochureById(_sokId)!;
        expect(catalog.skippedCount, 0);
        expect(sok.ocrProductsUrl, isNull);
        expect(sok.hasOcrProducts, isFalse);
      });
    }

    test('a brochure without pages has no OCR list', () {
      final json = _copy(sampleJson('catalog.json'));
      _brochureJson(json, 'migros-910')['ocr_products_url'] =
          'products_ocr/migros-910.json';
      final migros = Catalog.fromJson(json).brochureById('migros-910')!;
      expect(migros.ocrProductsUrl, isNull);
      expect(migros.productListSource, ProductSource.written);
    });

    test('with both lists the written one is the product list', () {
      final json = _copy(sampleJson('catalog.json'));
      _brochureJson(json, 'bim-2026-11-13-cuma')['ocr_products_url'] =
          'products_ocr/bim-2026-11-13-cuma.json';
      final bim = Catalog.fromJson(json).brochureById('bim-2026-11-13-cuma')!;
      expect(bim.hasProducts, isTrue);
      expect(bim.hasOcrProducts, isTrue);
      expect(bim.productListSource, ProductSource.written);
    });

    test('takes part in equality and hashCode', () {
      final a = _ocrBrochure('x');
      final b = _ocrBrochure('x');
      expect(a, b);
      expect(a.hashCode, b.hashCode);
      final plain = brochure('x', chainId: 'sok');
      expect(plain.ocrProductsUrl, isNull);
      expect(
        Brochure(
          id: a.id,
          chainId: a.chainId,
          title: a.title,
          dateLabel: a.dateLabel,
          validFrom: a.validFrom,
          validTo: a.validTo,
          kind: a.kind,
          cover: a.cover,
          pages: a.pages,
          productsUrl: a.productsUrl,
          productCount: a.productCount,
          sourceUrl: a.sourceUrl,
          firstSeen: a.firstSeen,
          updatedAt: a.updatedAt,
        ),
        isNot(a),
      );
    });
  });

  group('Product.source', () {
    test('missing source means the written list', () {
      final product = Product.fromJson(_productJson());
      expect(product.source, ProductSource.written);
      expect(product.isOcr, isFalse);
    });

    test('"ocr" marks an OCR product', () {
      final product = Product.fromJson(
        _productJson({'source': 'ocr', 'page_index': 2}),
      );
      expect(product.isOcr, isTrue);
      expect(product.pageIndex, 2);
    });

    test('takes part in equality and hashCode', () {
      final written = Product.fromJson(_productJson());
      final ocr = Product.fromJson(_productJson({'source': 'ocr'}));
      expect(written, isNot(ocr));
      expect(ocr, Product.fromJson(_productJson({'source': 'ocr'})));
      expect(
        ocr.hashCode,
        Product.fromJson(_productJson({'source': 'ocr'})).hashCode,
      );
    });

    for (final (name, extra) in <(String, Map<String, Object?>)>[
      ('an unknown source', {'source': 'api'}),
      ('a source of the wrong type', {'source': 1}),
      ('an OCR product without a page', {'source': 'ocr', 'page_index': null}),
      (
        'an OCR product with a negative page',
        {'source': 'ocr', 'page_index': -1},
      ),
    ]) {
      test('$name is skipped, never shown as a written price', () {
        final file = ProductFile.fromJson(
          _fileJson([_productJson(), _productJson(extra)]),
        );
        expect(file.products, hasLength(1));
        expect(file.products.single.isOcr, isFalse);
        expect(file.skippedCount, 1);
      });
    }

    test('a written file without page count keeps a bad written page', () {
      // Written products only lose their page link, as before.
      final product = Product.fromJson(_productJson({'page_index': -3}));
      expect(product.pageIndex, isNull);
      expect(product.isOcr, isFalse);
    });
  });

  group('OCR ProductFile', () {
    test('parses the sample Şok OCR file', () {
      final file = ProductFile.parse(
        sampleText('products_ocr/$_sokId.json'),
        source: ProductSource.ocr,
        pageCount: 4,
      );
      expect(file.isOcr, isTrue);
      expect(file.brochureId, _sokId);
      expect(file.skippedCount, 0);
      expect(file.products, hasLength(4));
      expect(file.products.every((p) => p.isOcr), isTrue);
      expect([for (final p in file.products) p.pageIndex], [0, 1, 1, 3]);
      expect(file.products.first.price.format(), '349,90 ₺');
      expect(file.products.first.discountPercent, 13);
    });

    test('every product of an OCR file is OCR, even without the field', () {
      final file = ProductFile.fromJson(
        _fileJson([_productJson()]),
        source: ProductSource.ocr,
      );
      expect(file.products.single.isOcr, isTrue);
    });

    test('a written file is written; a single OCR product keeps its flag', () {
      final file = ProductFile.fromJson(
        _fileJson([
          _productJson(),
          _productJson({'source': 'ocr'}),
        ]),
      );
      expect(file.isOcr, isFalse);
      expect([for (final p in file.products) p.isOcr], [false, true]);
    });

    test('an OCR product on a page the brochure lacks is skipped', () {
      final file = ProductFile.fromJson(
        _fileJson([
          _productJson({'page_index': 3}),
          _productJson({'page_index': 4}),
        ]),
        source: ProductSource.ocr,
        pageCount: 4,
      );
      expect([for (final p in file.products) p.pageIndex], [3]);
      expect(file.skippedCount, 1);
    });

    test('source takes part in equality', () {
      final body = sampleText('products_ocr/$_sokId.json');
      final ocr = ProductFile.parse(body, source: ProductSource.ocr);
      expect(ocr, ProductFile.parse(body, source: ProductSource.ocr));
      expect(
        ocr.hashCode,
        ProductFile.parse(body, source: ProductSource.ocr).hashCode,
      );
      final written = ProductFile.fromJson(
        _fileJson([
          _productJson({'source': 'ocr'}),
        ]),
      );
      final asOcr = ProductFile.fromJson(
        _fileJson([
          _productJson({'source': 'ocr'}),
        ]),
        source: ProductSource.ocr,
      );
      // Same products, different list.
      expect(listEquals(written.products, asOcr.products), isTrue);
      expect(written, isNot(asOcr));
    });
  });

  group('HttpCatalogRepository OCR list', () {
    late _Server server;
    late MemoryCacheStore cache;
    late HttpCatalogRepository repo;
    final ocrBody = sampleText('products_ocr/$_sokId.json');
    final sok = sampleCatalog().brochureById(_sokId)!;
    final ocrKey = 'products_ocr/$_sokId.json';

    setUp(() {
      server = _Server();
      cache = MemoryCacheStore();
      repo = HttpCatalogRepository(
        baseUrl: _base,
        client: server.client,
        cache: cache,
        timeout: const Duration(milliseconds: 100),
        now: () => DateTime.utc(2026, 11, 13, 10),
      );
    });

    test('cache keys of the two lists differ', () {
      expect(HttpCatalogRepository.ocrProductsCacheKey(_sokId), ocrKey);
      expect(
        HttpCatalogRepository.productsCacheKey(_sokId),
        isNot(HttpCatalogRepository.ocrProductsCacheKey(_sokId)),
      );
    });

    test('fetches, caches, revalidates and falls back offline', () async {
      server.respond(ocrBody, etag: '"o1"');
      final fresh = await repo.loadProducts(sok);
      expect(server.requests.single.url.toString(), '$_base/$ocrKey');
      expect(fresh.isOcr, isTrue);
      expect(fresh.products, hasLength(4));
      expect(fresh.products.every((p) => p.isOcr), isTrue);
      expect(cache.entries[ocrKey]!.etag, '"o1"');
      expect(cache.entries[ocrKey]!.body, ocrBody);
      expect(cache.entries.containsKey('products/$_sokId.json'), isFalse);

      server.notModified();
      expect(await repo.loadProducts(sok), fresh);
      expect(server.requests.last.headers['If-None-Match'], '"o1"');

      server.offline();
      final offline = await repo.loadProducts(sok);
      expect(offline, fresh);
      expect(offline.isOcr, isTrue);

      server.respond('not json');
      expect(await repo.loadProducts(sok), fresh);
      expect(cache.entries[ocrKey]!.body, ocrBody);
    });

    test('offline without a cached OCR file throws', () async {
      server.offline();
      await expectLater(
        repo.loadProducts(sok),
        throwsA(isA<ProductsUnavailableException>()),
      );
    });

    test('a cached written list never stands in for the OCR list', () async {
      // Same brochure id, written list cached under its own key.
      final writtenBody = jsonEncode(_fileJson([_productJson()]));
      await cache.write(
        HttpCatalogRepository.productsCacheKey(_sokId),
        CacheEntry(
          body: writtenBody,
          etag: '"w1"',
          fetchedAt: DateTime.utc(2026, 11, 13),
        ),
      );

      server.offline();
      await expectLater(
        repo.loadProducts(sok),
        throwsA(isA<ProductsUnavailableException>()),
      );

      server.respond(ocrBody, etag: '"o1"');
      final file = await repo.loadProducts(sok);
      expect(server.requests.last.headers['If-None-Match'], isNull);
      expect(file.isOcr, isTrue);
      expect(
        cache.entries[HttpCatalogRepository.productsCacheKey(_sokId)]!.body,
        writtenBody,
      );
    });

    test('with both lists only the written one is fetched', () async {
      final both = _ocrBrochure(
        'b1',
        chainId: 'bim',
        kind: BrochureKind.both,
        productsUrl: 'products/b1.json',
      );
      server.respond(jsonEncode(_fileJson([_productJson()])), etag: '"w"');
      final file = await repo.loadProducts(both);
      expect(server.requests.single.url.toString(), '$_base/products/b1.json');
      expect(file.isOcr, isFalse);
      expect(cache.entries.keys, ['products/b1.json']);
    });

    test('a brochure with neither list throws without a request', () async {
      final none = sampleCatalog().brochureById(
        'sok-2026-11-18-haftanin-firsatlari',
      )!;
      await expectLater(
        repo.loadProducts(none),
        throwsA(isA<ProductsUnavailableException>()),
      );
      expect(server.requests, isEmpty);
    });

    test('OCR products on pages the brochure lacks are dropped', () async {
      final twoPages = _ocrBrochure(_sokId, pageCount: 2);
      server.respond(ocrBody);
      final file = await repo.loadProducts(twoPages);
      expect([for (final p in file.products) p.pageIndex], [0, 1, 1]);
      expect(file.skippedCount, 1);
    });
  });

  group('AssetCatalogRepository OCR list', () {
    test('serves the bundled Şok OCR sample', () async {
      final assets = AssetCatalogRepository(rootBundle);
      final catalog = (await assets.loadCatalog()).catalog;
      final file = await assets.loadProducts(catalog.brochureById(_sokId)!);
      expect(file.isOcr, isTrue);
      expect(file.products, hasLength(4));
      expect(file.products.every((p) => p.isOcr), isTrue);
    });
  });

  group('productsProvider', () {
    setUp(() => SharedPreferences.setMockInitialValues({}));

    test('returns the OCR list of a page brochure', () async {
      final container = ProviderContainer.test(
        overrides: [
          catalogRepositoryProvider.overrideWithValue(
            AssetCatalogRepository(rootBundle),
          ),
          favoritesStoreProvider.overrideWithValue(MemoryFavoritesStore()),
          clockProvider.overrideWithValue(Clock.fixed(sampleToday)),
        ],
      );
      final file = await container.read(productsProvider(_sokId).future);
      expect(file.isOcr, isTrue);
      expect(file.products.first.name, 'Ayçiçek Yağı');
    });
  });

  group('search with OCR lists', () {
    final today = DateTime(2026, 11, 13);

    test('current and upcoming OCR lists are indexed, past ones not', () async {
      final repo = _Repo({
        'now': _file('now', [
          _ocr('Çay güncel', 100),
        ], source: ProductSource.ocr),
        'soon': _file('soon', [
          _ocr('Çay gelecek', 200),
        ], source: ProductSource.ocr),
        'old': _file('old', [
          _ocr('Çay geçmiş', 300),
        ], source: ProductSource.ocr),
      });
      final index = await buildSearchIndex(
        _catalog([
          _ocrBrochure('now', from: d(2026, 11, 10), to: d(2026, 11, 16)),
          _ocrBrochure('soon', from: d(2026, 11, 20), to: d(2026, 11, 26)),
          _ocrBrochure('old', from: d(2026, 11, 1), to: d(2026, 11, 7)),
        ]),
        today,
        repo,
      );
      expect(
        [for (final h in index.query('cay')) h.product.name],
        ['Çay güncel', 'Çay gelecek'],
      );
      expect(repo.requested, isNot(contains('old')));
      expect(index.query('cay').every((h) => h.isOcr), isTrue);
    });

    test('OCR and written products rank together by shelf price', () async {
      final repo = _Repo({
        'b1': _file('b1', [
          _written('Süt', 3000),
          _written('Sütlü Gofret', 50),
        ]),
        's1': _file('s1', [
          _ocr('Süt', 2500, page: 1),
          _ocr('Sütlaç', 40),
        ], source: ProductSource.ocr),
      });
      final index = await buildSearchIndex(
        _catalog([
          _ocrBrochure(
            'b1',
            chainId: 'bim',
            kind: BrochureKind.both,
            productsUrl: 'products/b1.json',
            from: d(2026, 11, 13),
            to: d(2026, 11, 19),
          ),
          _ocrBrochure('s1', from: d(2026, 11, 13), to: d(2026, 11, 19)),
        ]),
        today,
        repo,
      );
      final hits = index.query('süt');
      expect(
        [for (final h in hits) (h.product.name, h.chain.id, h.isOcr)],
        [
          ('Süt', 'sok', true),
          ('Süt', 'bim', false),
          ('Sütlaç', 'sok', true),
          ('Sütlü Gofret', 'bim', false),
        ],
      );
    });

    test('chains with only OCR products are searchable chains', () async {
      final repo = _Repo({
        's1': _file('s1', [_ocr('Çay', 100)], source: ProductSource.ocr),
        'm1': _file('m1', [_written('Süt', 100)]),
      });
      final migros = Brochure(
        id: 'm1',
        chainId: 'migros',
        title: 'm1',
        dateLabel: null,
        validFrom: d(2026, 11, 10),
        validTo: null,
        kind: BrochureKind.products,
        cover: null,
        pages: const [],
        productsUrl: 'products/m1.json',
        productCount: 1,
        sourceUrl: 'https://example.com',
        firstSeen: DateTime.utc(2026, 11, 1, 12),
        updatedAt: DateTime.utc(2026, 11, 1, 12),
      );
      final index = await buildSearchIndex(
        _catalog([
          _ocrBrochure('s1', from: d(2026, 11, 10)),
          migros,
          // A page brochure without any list is still not loaded.
          brochure('p1', from: d(2026, 11, 10)),
        ]),
        today,
        repo,
      );
      expect([for (final c in index.chains) c.id], ['sok', 'migros']);
      expect(repo.requested, unorderedEquals(['s1', 'm1']));
    });

    test('an OCR hit opens the brochure on its page', () async {
      final repo = _Repo({
        's1': _file('s1', [
          _ocr('Toz Deterjan', 129900, page: 3),
        ], source: ProductSource.ocr),
      });
      final index = await buildSearchIndex(
        _catalog([_ocrBrochure('s1', from: d(2026, 11, 10))]),
        today,
        repo,
      );
      final hit = index.query('deterjan').single;
      expect(hit.isOcr, isTrue);
      expect(searchHitPage(hit), 3);
    });

    test('the bundled sample makes Şok searchable with page links', () async {
      final assets = AssetCatalogRepository(rootBundle);
      final catalog = (await assets.loadCatalog()).catalog;
      final index = await buildSearchIndex(catalog, sampleToday, assets);

      expect([for (final c in index.chains) c.id], contains('sok'));
      final omo = index.query('omo').single;
      expect(omo.chain.id, 'sok');
      expect(omo.brochure.id, _sokId);
      expect(omo.isOcr, isTrue);
      expect(omo.product.price.format(), '1.299,00 ₺');
      expect(searchHitPage(omo), 3);

      final lastik = index.query('lastik');
      expect([for (final h in lastik) searchHitPage(h)], [1, 1]);
      expect(lastik.every((h) => h.isOcr), isTrue);

      // Written lists stay unlabelled.
      final bim = index.query('toz şeker');
      expect(bim, isNotEmpty);
      expect(bim.every((h) => !h.isOcr), isTrue);
    });

    test(
      'without ocr_products_url (older catalog) Şok is not indexed',
      () async {
        final json = _copy(sampleJson('catalog.json'));
        _brochureJson(json, _sokId).remove('ocr_products_url');
        final assets = AssetCatalogRepository(rootBundle);
        final index = await buildSearchIndex(
          Catalog.fromJson(json),
          sampleToday,
          assets,
        );
        expect([for (final c in index.chains) c.id], isNot(contains('sok')));
        expect(index.query('omo'), isEmpty);
      },
    );
  });
}
