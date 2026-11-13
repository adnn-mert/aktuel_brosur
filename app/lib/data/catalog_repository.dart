import 'dart:async';
import 'dart:convert';

import 'package:flutter/services.dart' show AssetBundle;
import 'package:http/http.dart' as http;

import 'cache_store.dart';
import 'errors.dart';
import 'models/brochure.dart';
import 'models/catalog.dart';
import 'models/product.dart';

/// Where a [CatalogResult] came from.
enum CatalogSource {
  /// Downloaded just now.
  network,

  /// Read from the on-device copy (either the server said "not modified" or
  /// the network failed; check [CatalogResult.isStale] to tell them apart).
  cache,

  /// The sample data bundled with the app (development builds).
  bundledSample,
}

/// A catalog plus how fresh it is.
class CatalogResult {
  const CatalogResult({
    required this.catalog,
    required this.source,
    required this.fetchedAt,
    this.isStale = false,
  });

  final Catalog catalog;
  final CatalogSource source;

  /// When this data was last confirmed current by the server (UTC). For a
  /// stale result this is the time of the last successful download.
  final DateTime fetchedAt;

  /// True when the network could not be reached (or answered garbage) and an
  /// older cached copy is shown instead. The UI should say so.
  final bool isStale;

  @override
  bool operator ==(Object other) =>
      other is CatalogResult &&
      other.catalog == catalog &&
      other.source == source &&
      other.fetchedAt == fetchedAt &&
      other.isStale == isStale;

  @override
  int get hashCode => Object.hash(catalog, source, fetchedAt, isStale);

  @override
  String toString() =>
      'CatalogResult($source, stale: $isStale, fetchedAt: $fetchedAt)';
}

/// The single entry point for reading published data.
abstract class CatalogRepository {
  /// Returns the freshest catalog available. Never throws when a cached copy
  /// exists; otherwise throws [CatalogUnavailableException].
  ///
  /// [forceRefresh] skips conditional-request shortcuts and downloads the
  /// full file.
  Future<CatalogResult> loadCatalog({bool forceRefresh = false});

  /// Loads the product list of [brochure]. Falls back to a cached copy when
  /// offline; throws [ProductsUnavailableException] when there is none or
  /// the brochure has no product list.
  Future<ProductFile> loadProducts(Brochure brochure);

  /// Resolves an absolute or catalog-relative URL from the JSON to a fetchable
  /// Uri.
  Uri resolve(String url);
}

/// Reads `catalog.json` and product files over HTTP, keeping the last good
/// copy of each on disk for offline use.
class HttpCatalogRepository implements CatalogRepository {
  /// [baseUrl] is the folder that holds `catalog.json`, e.g.
  /// `https://<user>.github.io/aktuel_brosur/`.
  HttpCatalogRepository({
    required String baseUrl,
    required this.client,
    required this.cache,
    this.timeout = const Duration(seconds: 15),
    DateTime Function()? now,
  }) : baseUri = Uri.parse(baseUrl.endsWith('/') ? baseUrl : '$baseUrl/'),
       _now = now ?? DateTime.now;

  static const String catalogKey = 'catalog.json';

  final Uri baseUri;
  final Duration timeout;
  final http.Client client;
  final CacheStore cache;
  final DateTime Function() _now;

  @override
  Uri resolve(String url) => _resolveAgainst(baseUri, url);

  @override
  Future<CatalogResult> loadCatalog({bool forceRefresh = false}) async {
    final uri = resolve(catalogKey);
    final cached = await cache.read(catalogKey);
    final cachedCatalog = _tryParse(cached?.body, Catalog.parse);

    var fetched = await _fetch(
      uri,
      // Only revalidate a copy we can actually read back.
      etag: forceRefresh || cachedCatalog == null ? null : cached?.etag,
      parse: Catalog.parse,
    );
    if (fetched is _NotModified<Catalog>) {
      if (cachedCatalog != null) {
        final fetchedAt = _now().toUtc();
        await _safeWrite(catalogKey, cached!.copyWith(fetchedAt: fetchedAt));
        return CatalogResult(
          catalog: cachedCatalog,
          source: CatalogSource.cache,
          fetchedAt: fetchedAt,
        );
      }
      fetched = const _Failed<Catalog>('HTTP 304 without a usable cached copy');
    }

    switch (fetched) {
      case _Fresh(:final value, :final body, :final etag):
        final fetchedAt = _now().toUtc();
        await _safeWrite(
          catalogKey,
          CacheEntry(body: body, etag: etag, fetchedAt: fetchedAt),
        );
        return CatalogResult(
          catalog: value,
          source: CatalogSource.network,
          fetchedAt: fetchedAt,
        );
      case _NotModified():
      case _Failed():
        if (cachedCatalog == null) {
          throw CatalogUnavailableException(
            'catalog.json could not be loaded and no cached copy exists',
            fetched is _Failed<Catalog> ? fetched.error : null,
          );
        }
        return CatalogResult(
          catalog: cachedCatalog,
          source: CatalogSource.cache,
          fetchedAt: cached!.fetchedAt,
          isStale: true,
        );
    }
  }

  @override
  Future<ProductFile> loadProducts(Brochure brochure) async {
    final path = brochure.productsUrl;
    if (path == null) {
      throw ProductsUnavailableException(
        'brochure ${brochure.id} has no product list',
      );
    }
    final key = productsCacheKey(brochure.id);
    final cached = await cache.read(key);
    final cachedFile = _tryParse(cached?.body, ProductFile.parse);

    final fetched = await _fetch(
      resolve(path),
      etag: cachedFile == null ? null : cached?.etag,
      parse: ProductFile.parse,
    );
    switch (fetched) {
      case _Fresh(:final value, :final body, :final etag):
        await _safeWrite(
          key,
          CacheEntry(body: body, etag: etag, fetchedAt: _now().toUtc()),
        );
        return value;
      case _NotModified():
      case _Failed():
        if (cachedFile != null) return cachedFile;
        throw ProductsUnavailableException(
          'products of ${brochure.id} could not be loaded',
          fetched is _Failed<ProductFile> ? fetched.error : null,
        );
    }
  }

  /// Cache key of a brochure's product file.
  static String productsCacheKey(String brochureId) =>
      'products/$brochureId.json';

  /// One GET with an optional conditional header and a timeout. Never throws:
  /// every failure (socket, timeout, non-200, unparsable body) becomes
  /// [_Failed], which callers turn into a cache fallback. A body is reported
  /// as [_Fresh] only after it parsed, so a broken file never replaces a good
  /// cached one.
  Future<_Fetch<T>> _fetch<T>(
    Uri uri, {
    required String? etag,
    required T Function(String body) parse,
  }) async {
    try {
      final response = await client
          .get(uri, headers: {'If-None-Match': ?etag})
          .timeout(timeout);
      if (response.statusCode == 304) return _NotModified<T>();
      if (response.statusCode != 200) {
        return _Failed<T>('HTTP ${response.statusCode} for $uri');
      }
      // GitHub Pages may omit the charset; the files are always UTF-8.
      final body = utf8.decode(response.bodyBytes);
      return _Fresh<T>(parse(body), body, response.headers['etag']);
    } on Object catch (e) {
      // TimeoutException, SocketException, ClientException, parse errors...
      return _Failed<T>(e);
    }
  }

  T? _tryParse<T>(String? body, T Function(String) parse) {
    if (body == null || body.isEmpty) return null;
    try {
      return parse(body);
    } on Object {
      return null;
    }
  }

  Future<void> _safeWrite(String key, CacheEntry entry) async {
    try {
      await cache.write(key, entry);
    } on Object {
      // A full disk must not hide data we already have in hand.
    }
  }
}

sealed class _Fetch<T> {
  const _Fetch();
}

class _Fresh<T> extends _Fetch<T> {
  const _Fresh(this.value, this.body, this.etag);

  final T value;
  final String body;
  final String? etag;
}

class _NotModified<T> extends _Fetch<T> {
  const _NotModified();
}

class _Failed<T> extends _Fetch<T> {
  const _Failed(this.error);

  final Object error;
}

/// Serves the sample data bundled under `assets/sample/` (used when the app
/// is built without `--dart-define=CATALOG_BASE_URL=...`).
///
/// Catalog-relative URLs resolve to `asset:` URIs (see [isBundledAsset]);
/// absolute https URLs are returned unchanged.
class AssetCatalogRepository implements CatalogRepository {
  AssetCatalogRepository(
    this._bundle, {
    this.basePath = 'assets/sample/',
    DateTime Function()? now,
  }) : _now = now ?? DateTime.now;

  final AssetBundle _bundle;

  /// Asset folder that plays the role of the catalog's base URL.
  final String basePath;
  final DateTime Function() _now;

  Future<String> _loadText(String key) async {
    // load + decode instead of loadString: loadString moves big files to a
    // background isolate, which stalls inside widget tests.
    final data = await _bundle.load(key);
    return utf8.decode(
      data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes),
    );
  }

  @override
  Future<CatalogResult> loadCatalog({bool forceRefresh = false}) async {
    final String body;
    try {
      body = await _loadText('${basePath}catalog.json');
    } on Object catch (e) {
      throw CatalogUnavailableException('bundled sample catalog missing', e);
    }
    return CatalogResult(
      catalog: Catalog.parse(body),
      source: CatalogSource.bundledSample,
      fetchedAt: _now().toUtc(),
    );
  }

  @override
  Future<ProductFile> loadProducts(Brochure brochure) async {
    final path = brochure.productsUrl;
    if (path == null) {
      throw ProductsUnavailableException(
        'brochure ${brochure.id} has no product list',
      );
    }
    final uri = resolve(path);
    if (!uri.isBundledAsset) {
      throw ProductsUnavailableException(
        'sample product file must be a relative path: $path',
      );
    }
    try {
      return ProductFile.parse(await _loadText(uri.assetKey));
    } on CatalogFormatException {
      rethrow;
    } on Object catch (e) {
      throw ProductsUnavailableException(
        'sample products of ${brochure.id} missing',
        e,
      );
    }
  }

  @override
  Uri resolve(String url) =>
      _resolveAgainst(Uri(scheme: 'asset', path: basePath), url);
}

/// Absolute `https://`/`http://` URLs pass through; anything else is taken as
/// relative to [base].
Uri _resolveAgainst(Uri base, String url) {
  final parsed = Uri.parse(url.trim());
  if (parsed.hasScheme) return parsed;
  return base.resolveUri(parsed);
}

/// Helpers for URIs produced by [CatalogRepository.resolve].
extension BundledAssetUri on Uri {
  /// True for sample-data files shipped inside the app (`asset:` scheme).
  /// Load them with `Image.asset(uri.assetKey)` / `rootBundle`, not over HTTP.
  bool get isBundledAsset => scheme == 'asset';

  /// The asset key (e.g. `assets/sample/media/sok/x/p01.webp`).
  String get assetKey => path;
}
