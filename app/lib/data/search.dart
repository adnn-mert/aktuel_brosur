/// Product search over every current and upcoming brochure.
///
/// The index lives in memory and is built from the catalog plus the products
/// files (loaded through the repository, so caching and offline behaviour are
/// the same as on the product list screen). See `README.md` for usage.
library;

import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'brochure_grouping.dart';
import 'catalog_repository.dart';
import 'models/brochure.dart';
import 'models/catalog.dart';
import 'models/chain.dart';
import 'models/product.dart';
import 'providers.dart';

/// One search result: a product with the brochure and chain it appears in.
class SearchHit {
  const SearchHit({
    required this.product,
    required this.chain,
    required this.brochure,
  });

  final Product product;
  final Chain chain;
  final Brochure brochure;

  /// True when the price was read from the brochure page by OCR: show the
  /// "broşürden okundu" label; [Product.pageIndex] names the page.
  bool get isOcr => product.isOcr;

  @override
  String toString() => 'SearchHit(${product.name}, ${chain.id})';
}

// Turkish-aware lower-casing first (Dart's toLowerCase maps İ to "i" plus a
// combining dot and I to "i", which would merge two different Turkish
// letters), then every Turkish letter is folded to its ASCII look-alike so
// "cay" finds "Çay" and "ISIRGAN" finds "ısırgan".
const Map<String, String> _fold = {
  'ı': 'i',
  'ç': 'c',
  'ğ': 'g',
  'ö': 'o',
  'ş': 's',
  'ü': 'u',
  'â': 'a',
  'î': 'i',
  'û': 'u',
};

final RegExp _foldable = RegExp('[ıçğöşüâîû]');
final RegExp _notWordChar = RegExp(r'[^\p{L}\p{N}]+', unicode: true);

/// Normalises [text] for searching: lower-case (Turkish rules), Turkish
/// letters folded to ASCII, everything that is not a letter or digit turned
/// into a single space. `normalizeForSearch('İSTANBUL ÇAYI!') == 'istanbul cayi'`.
String normalizeForSearch(String text) {
  final lower = text
      .replaceAll('I', 'ı')
      .replaceAll('İ', 'i')
      .toLowerCase()
      .replaceAll('̇', '');
  final folded = lower.replaceAllMapped(_foldable, (m) => _fold[m[0]]!);
  return folded.replaceAll(_notWordChar, ' ').trim();
}

List<String> _words(String text) {
  final normalised = normalizeForSearch(text);
  return normalised.isEmpty ? const [] : normalised.split(' ');
}

class _Entry {
  _Entry(this.hit)
    : words = _words('${hit.product.name} ${hit.product.brand ?? ''}');

  final SearchHit hit;
  final List<String> words;

  bool matchesAll(List<String> prefixes) =>
      prefixes.every((p) => words.any((w) => w.startsWith(p)));

  // Whole-word match: "sut" is exact for "Süt" but not for "Sütlü".
  bool matchesAllExactly(List<String> queryWords) =>
      queryWords.every(words.contains);
}

/// Searchable snapshot of every product in the current and upcoming
/// brochures.
class SearchIndex {
  /// Builds an index from [hits]; [catalogChains] gives the order of
  /// [chains]. Hits without a positive shelf price are dropped (a product
  /// without a price cannot be ranked or shown).
  factory SearchIndex.fromHits(
    Iterable<SearchHit> hits,
    List<Chain> catalogChains,
  ) {
    final entries = [
      for (final hit in hits)
        if (hit.product.price.minor > 0) _Entry(hit),
    ];
    // Shelf price only: the member price never decides the order.
    entries.sort((a, b) {
      var c = a.hit.product.price.minor.compareTo(b.hit.product.price.minor);
      if (c != 0) return c;
      c = compareTurkish(a.hit.product.name, b.hit.product.name);
      if (c != 0) return c;
      return a.hit.brochure.id.compareTo(b.hit.brochure.id);
    });
    final withProducts = {for (final e in entries) e.hit.chain.id};
    return SearchIndex._(
      entries,
      List.unmodifiable([
        for (final c in catalogChains)
          if (withProducts.contains(c.id)) c,
      ]),
    );
  }

  const SearchIndex._(this._entries, this.chains);

  final List<_Entry> _entries;

  /// Number of searchable products.
  int get productCount => _entries.length;

  /// Chains with at least one searchable product, in catalog order.
  final List<Chain> chains;

  /// Products whose name or brand contains every word of [text] as a word
  /// prefix. Hits where every query word is a whole word come first (so
  /// "süt" lists milk before "Sütlü" chocolate); each tier is sorted by
  /// cheapest shelf price, then by name. Empty or blank [text] gives an empty
  /// list.
  List<SearchHit> query(String text) {
    final queryWords = _words(text);
    if (queryWords.isEmpty) return const [];
    // _entries is already in price order, so a stable split keeps it per tier.
    final exact = <SearchHit>[];
    final prefixOnly = <SearchHit>[];
    for (final e in _entries) {
      if (!e.matchesAll(queryWords)) continue;
      (e.matchesAllExactly(queryWords) ? exact : prefixOnly).add(e.hit);
    }
    return List.unmodifiable([...exact, ...prefixOnly]);
  }
}

// Products files are loaded a few at a time: all of them at once would open
// dozens of connections on a first (uncached) run.
const int _maxParallelLoads = 6;

/// Builds the index for [catalog] as of [today]: every current or upcoming
/// brochure with a product list ([Brochure.hasProductList]: the written
/// `products_url`, otherwise the OCR `ocr_products_url`) contributes its
/// products. A products file that cannot be loaded is skipped.
Future<SearchIndex> buildSearchIndex(
  Catalog catalog,
  DateTime today,
  CatalogRepository repository,
) async {
  final groups = groupBrochures(catalog.brochures, today);
  final brochures = [
    for (final b in [...groups.current, ...groups.upcoming])
      if (b.hasProductList) b,
  ];

  final files = List<ProductFile?>.filled(brochures.length, null);
  var next = 0;
  Future<void> worker() async {
    while (next < brochures.length) {
      final i = next++;
      try {
        files[i] = await repository.loadProducts(brochures[i]);
      } on Object {
        // One broken file must not take the whole search down.
      }
    }
  }

  await Future.wait([for (var i = 0; i < _maxParallelLoads; i++) worker()]);

  final hits = <SearchHit>[];
  for (var i = 0; i < brochures.length; i++) {
    final file = files[i];
    if (file == null) continue;
    final brochure = brochures[i];
    final chain = catalog.chainById(brochure.chainId);
    if (chain == null) continue;
    for (final product in file.products) {
      hits.add(SearchHit(product: product, chain: chain, brochure: brochure));
    }
  }
  return SearchIndex.fromHits(hits, catalog.chains);
}

Duration? _noRetry(int retryCount, Object error) => null;

/// The product search index. Loading while products files are fetched (cached
/// ones are instant); error only when the catalog itself failed. Rebuilt when
/// the catalog or the calendar day changes.
final searchIndexProvider = FutureProvider<SearchIndex>((ref) async {
  final today = ref.watch(clockProvider).today();
  final repository = ref.watch(catalogRepositoryProvider);
  final result = await ref.watch(catalogProvider.future);
  return buildSearchIndex(result.catalog, today, repository);
}, retry: _noRetry);
