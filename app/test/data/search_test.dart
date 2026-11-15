import 'package:aktuel_brosur/data/data.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../helpers.dart';

final DateTime _today = DateTime(2026, 11, 13);

Brochure _withProducts(
  String id, {
  String chainId = 'bim',
  DateTime? from,
  DateTime? to,
  String? productsUrl,
}) {
  final base = brochure(id, chainId: chainId, from: from, to: to);
  return Brochure(
    id: id,
    chainId: chainId,
    title: id,
    dateLabel: null,
    validFrom: from,
    validTo: to,
    kind: BrochureKind.products,
    cover: null,
    pages: const [],
    productsUrl: productsUrl ?? 'products/$id.json',
    productCount: 1,
    sourceUrl: base.sourceUrl,
    firstSeen: base.firstSeen,
    updatedAt: base.updatedAt,
  );
}

Product _product(String name, int minor, {String? brand, int? memberMinor}) =>
    Product(
      name: name,
      brand: brand,
      price: Money(minor),
      memberPrice: memberMinor == null ? null : Money(memberMinor),
      memberPriceLabel: memberMinor == null ? null : 'Money ile',
    );

class _Repo implements CatalogRepository {
  _Repo(this.files);

  final Map<String, List<Product>> files;
  final List<String> requested = [];

  @override
  Future<CatalogResult> loadCatalog({bool forceRefresh = false}) =>
      throw UnimplementedError();

  @override
  Future<ProductFile> loadProducts(Brochure brochure) async {
    requested.add(brochure.id);
    final products = files[brochure.id];
    if (products == null) throw ProductsUnavailableException(brochure.id);
    return ProductFile(
      schemaVersion: 1,
      brochureId: brochure.id,
      currency: 'TRY',
      products: products,
    );
  }

  @override
  Uri resolve(String url) => Uri.parse(url);
}

Catalog _catalog(List<Chain> chains, List<Brochure> brochures) => Catalog(
  schemaVersion: 1,
  generatedAt: DateTime.utc(2026, 11, 13),
  minAppVersion: 1,
  chains: chains,
  brochures: brochures,
);

Future<SearchIndex> _index(
  Map<String, List<Product>> files,
  List<Brochure> brochures, {
  List<Chain>? chains,
  _Repo? repo,
}) => buildSearchIndex(
  _catalog(
    chains ?? [chain('bim', name: 'BİM'), chain('migros', name: 'Migros')],
    brochures,
  ),
  _today,
  repo ?? _Repo(files),
);

List<String> _names(SearchIndex index, String text) => [
  for (final h in index.query(text)) h.product.name,
];

void main() {
  group('normalizeForSearch', () {
    test('handles the four Turkish i letters', () {
      expect(normalizeForSearch('İ'), 'i');
      expect(normalizeForSearch('I'), 'i');
      expect(normalizeForSearch('ı'), 'i');
      expect(normalizeForSearch('i'), 'i');
    });

    test('lower-cases, folds letters and drops punctuation', () {
      expect(normalizeForSearch('İSTANBUL ÇAYI'), 'istanbul cayi');
      expect(normalizeForSearch('Ğ Ö Ş Ü'), 'g o s u');
      expect(normalizeForSearch('Süt, 1,5 L (%3)!'), 'sut 1 5 l 3');
      expect(normalizeForSearch('  ...  '), '');
    });
  });

  group('SearchIndex.query', () {
    late SearchIndex index;

    setUp(() async {
      index = await _index(
        {
          'b1': [
            _product('Süt 1 L', 4500, brand: 'Pınar'),
            _product('Çay 500 g', 9000, brand: 'Doğuş'),
            _product('ISIRGAN otu', 3000),
            _product('Siyah Çay Demlik Poşet', 12000, brand: 'Rize'),
          ],
        },
        [_withProducts('b1', from: d(2026, 11, 13), to: d(2026, 11, 19))],
      );
    });

    test('empty and blank text give no results', () {
      expect(index.query(''), isEmpty);
      expect(index.query('   '), isEmpty);
      expect(index.query('...'), isEmpty);
    });

    test('upper-case ASCII finds Turkish letters', () {
      expect(_names(index, 'SÜT'), ['Süt 1 L']);
      expect(_names(index, 'SUT'), ['Süt 1 L']);
      expect(_names(index, 'sut'), ['Süt 1 L']);
    });

    test('ASCII finds Ç', () {
      expect(_names(index, 'cay'), ['Çay 500 g', 'Siyah Çay Demlik Poşet']);
    });

    test('dotted and dotless I both match', () {
      expect(_names(index, 'ISIRGAN'), ['ISIRGAN otu']);
      expect(_names(index, 'ısırgan'), ['ISIRGAN otu']);
      expect(_names(index, 'isirgan'), ['ISIRGAN otu']);
      expect(_names(index, 'İSİRGAN'), ['ISIRGAN otu']);
    });

    test('matches the start of a word, not the middle', () {
      expect(_names(index, 'ay'), isEmpty);
      expect(_names(index, 'pin'), ['Süt 1 L']); // brand Pınar
    });

    test('every word must match, in any order', () {
      expect(_names(index, 'cay siyah'), ['Siyah Çay Demlik Poşet']);
      expect(_names(index, 'siyah dem'), ['Siyah Çay Demlik Poşet']);
      expect(_names(index, 'cay sut'), isEmpty);
    });

    test('brand is searchable', () {
      expect(_names(index, 'dogus'), ['Çay 500 g']);
      expect(_names(index, 'rize cay'), ['Siyah Çay Demlik Poşet']);
    });

    test('punctuation in the query is ignored', () {
      expect(_names(index, '  süt!! '), ['Süt 1 L']);
    });

    test('hits carry the product, chain and brochure', () {
      final hit = index.query('sut').single;
      expect(hit.chain.id, 'bim');
      expect(hit.brochure.id, 'b1');
      expect(hit.product.price, const Money(4500));
    });
  });

  group('sorting', () {
    test('cheapest shelf price first, ties by Turkish name', () async {
      final index = await _index(
        {
          'b1': [
            _product('Çay C', 5000),
            _product('Çay B', 2000),
            _product('Çay Z', 5000),
            _product('Çay Ç', 5000),
          ],
        },
        [_withProducts('b1', from: d(2026, 11, 13), to: d(2026, 11, 19))],
      );
      expect(_names(index, 'cay'), ['Çay B', 'Çay C', 'Çay Ç', 'Çay Z']);
    });

    test('member price never decides the order', () async {
      final index = await _index(
        {
          'b1': [
            _product('Çay A', 5000, memberMinor: 100),
            _product('Çay B', 3000),
          ],
        },
        [_withProducts('b1', from: d(2026, 11, 13), to: d(2026, 11, 19))],
      );
      expect(_names(index, 'cay'), ['Çay B', 'Çay A']);
    });

    test('mixes chains and brochures by price', () async {
      final index = await _index(
        {
          'b1': [_product('Çay', 5000)],
          'm1': [_product('Çay', 4000)],
        },
        [
          _withProducts('b1', from: d(2026, 11, 13), to: d(2026, 11, 19)),
          _withProducts(
            'm1',
            chainId: 'migros',
            from: d(2026, 11, 13),
            to: d(2026, 11, 19),
          ),
        ],
      );
      expect(
        [for (final h in index.query('cay')) h.chain.id],
        ['migros', 'bim'],
      );
    });

    test('products without a price are excluded', () async {
      final index = await _index(
        {
          'b1': [_product('Çay Bedava', 0), _product('Çay', 100)],
        },
        [_withProducts('b1', from: d(2026, 11, 13), to: d(2026, 11, 19))],
      );
      expect(_names(index, 'cay'), ['Çay']);
      expect(index.productCount, 1);
    });
  });

  group('ranking tiers', () {
    Future<SearchIndex> indexOf(List<Product> products) => _index(
      {'b1': products},
      [_withProducts('b1', from: d(2026, 11, 13), to: d(2026, 11, 19))],
    );

    test('whole-word match outranks a cheaper prefix match', () async {
      final index = await indexOf([
        _product('Sütlü Çikolatalı Gofret', 800),
        _product('Tam Yağlı Süt 1 L', 4500),
      ]);
      expect(_names(index, 'süt'), [
        'Tam Yağlı Süt 1 L',
        'Sütlü Çikolatalı Gofret',
      ]);
    });

    test('within a tier the cheaper one comes first', () async {
      final index = await indexOf([
        _product('Süt B', 5000),
        _product('Sütlü Gofret', 100),
        _product('Süt A', 3000),
        _product('Sütlaç', 200),
      ]);
      expect(_names(index, 'süt'), [
        'Süt A',
        'Süt B',
        'Sütlü Gofret',
        'Sütlaç',
      ]);
    });

    test('a query word that is only a prefix drops the hit to tier 2', () async {
      final index = await indexOf([
        _product('Siyah Çay Demlik Poşet', 9000),
        _product('Siyah Çaylı Bisküvi', 100),
        _product('Yeşil Çay Siyah Biber', 4000),
      ]);
      // "cay" is a prefix of "Çaylı" only, so that hit is tier 2.
      expect(_names(index, 'siyah cay'), [
        'Yeşil Çay Siyah Biber',
        'Siyah Çay Demlik Poşet',
        'Siyah Çaylı Bisküvi',
      ]);
    });

    test('Turkish case folding applies to whole-word matches', () async {
      final index = await indexOf([
        _product('Çaylı Bisküvi', 100),
        _product('Rize Çay 500 g', 9000),
        _product('Sütlü Gofret', 100),
        _product('Süt 1 L', 4500),
      ]);
      expect(_names(index, 'ÇAY'), ['Rize Çay 500 g', 'Çaylı Bisküvi']);
      expect(_names(index, 'SÜT'), ['Süt 1 L', 'Sütlü Gofret']);
    });

    test('brand words count as whole words; member price is ignored', () async {
      final index = await indexOf([
        _product('Peynir', 3000, brand: 'Sütaş', memberMinor: 50),
        _product('Yoğurt', 6000, brand: 'Süt'),
        _product('Ayran', 4000, brand: 'Süt'),
      ]);
      expect(_names(index, 'süt'), ['Ayran', 'Yoğurt', 'Peynir']);
    });
  });

  group('which brochures are indexed', () {
    test('current and upcoming yes, past no', () async {
      final repo = _Repo({
        'now': [_product('Çay güncel', 100)],
        'soon': [_product('Çay gelecek', 200)],
        'old': [_product('Çay geçmiş', 300)],
      });
      final index = await _index(const {}, [
        _withProducts('now', from: d(2026, 11, 10), to: d(2026, 11, 16)),
        _withProducts('soon', from: d(2026, 11, 20), to: d(2026, 11, 26)),
        _withProducts('old', from: d(2026, 11, 1), to: d(2026, 11, 7)),
      ], repo: repo);
      expect(_names(index, 'cay'), ['Çay güncel', 'Çay gelecek']);
      expect(repo.requested, isNot(contains('old')));
    });

    test('brochures without products_url are not loaded', () async {
      final repo = _Repo({
        'p': [_product('Çay', 100)],
      });
      final pages = brochure(
        'pages-only',
        from: d(2026, 11, 10),
        to: d(2026, 11, 16),
      );
      final index = await _index(const {}, [
        pages,
        _withProducts('p', from: d(2026, 11, 10), to: d(2026, 11, 16)),
      ], repo: repo);
      expect(repo.requested, ['p']);
      expect(index.productCount, 1);
    });

    test('a failed products file is skipped, the rest is indexed', () async {
      final index = await _index(
        {
          'ok': [_product('Çay', 100)],
          // 'broken' has no entry, so loading throws.
        },
        [
          _withProducts('broken', from: d(2026, 11, 10), to: d(2026, 11, 16)),
          _withProducts('ok', from: d(2026, 11, 10), to: d(2026, 11, 16)),
        ],
      );
      expect(_names(index, 'cay'), ['Çay']);
    });
  });

  group('chains', () {
    test('only chains with products, in catalog order', () async {
      final index = await _index(
        {
          'm1': [_product('Çay', 100)],
          'b1': [_product('Süt', 100)],
        },
        [
          _withProducts('m1', chainId: 'migros', from: d(2026, 11, 10)),
          _withProducts('b1', from: d(2026, 11, 10)),
        ],
        chains: [
          chain('a101', name: 'A101'),
          chain('bim', name: 'BİM'),
          chain('migros', name: 'Migros'),
        ],
      );
      expect([for (final c in index.chains) c.id], ['bim', 'migros']);
    });

    test('a chain whose only products file failed is not listed', () async {
      final index = await _index(
        {
          'b1': [_product('Süt', 100)],
        },
        [
          _withProducts('b1', from: d(2026, 11, 10)),
          _withProducts('m1', chainId: 'migros', from: d(2026, 11, 10)),
        ],
      );
      expect([for (final c in index.chains) c.id], ['bim']);
    });
  });

  group('searchIndexProvider', () {
    ProviderContainer containerWith(CatalogRepository repo) =>
        ProviderContainer.test(
          overrides: [
            catalogRepositoryProvider.overrideWithValue(repo),
            favoritesStoreProvider.overrideWithValue(MemoryFavoritesStore()),
            clockProvider.overrideWithValue(Clock.fixed(_today)),
          ],
        );

    setUp(() => SharedPreferences.setMockInitialValues({}));

    test('builds from the catalog', () async {
      final repo = _ProviderRepo(
        catalog: _catalog(
          [chain('bim')],
          [_withProducts('b1', from: d(2026, 11, 10), to: d(2026, 11, 16))],
        ),
        files: {
          'b1': [_product('Süt', 100)],
        },
      );
      final index = await containerWith(repo).read(searchIndexProvider.future);
      expect(index.productCount, 1);
      expect(_names(index, 'SÜT'), ['Süt']);
    });

    test('is an error when the catalog fails', () async {
      final repo = _ProviderRepo(
        catalogError: const CatalogUnavailableException('offline'),
      );
      final container = containerWith(repo);
      await expectLater(
        container.read(searchIndexProvider.future),
        throwsA(isA<CatalogUnavailableException>()),
      );
    });
  });
}

class _ProviderRepo extends _Repo {
  _ProviderRepo({
    this.catalog,
    this.catalogError,
    Map<String, List<Product>>? files,
  }) : super(files ?? {});

  final Catalog? catalog;
  final Object? catalogError;

  @override
  Future<CatalogResult> loadCatalog({bool forceRefresh = false}) async {
    final error = catalogError;
    if (error != null) throw error;
    return CatalogResult(
      catalog: catalog!,
      source: CatalogSource.network,
      fetchedAt: DateTime.utc(2026, 11, 13, 10),
      isStale: false,
    );
  }
}
