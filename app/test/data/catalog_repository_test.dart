import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:aktuel_brosur/data/cache_store.dart' show FileCacheStore;
import 'package:aktuel_brosur/data/data.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import '../helpers.dart';

const _base = 'https://example.github.io/aktuel_brosur';

/// Scripted server: each request is answered by the next handler.
class _Server {
  final List<Future<http.Response> Function(http.Request)> handlers = [];
  final List<http.Request> requests = [];

  late final http.Client client = MockClient((request) {
    requests.add(request);
    if (handlers.isEmpty) fail('unexpected request ${request.url}');
    return handlers.removeAt(0)(request);
  });

  void respond(String body, {int status = 200, String? etag}) {
    handlers.add(
      (_) async => http.Response.bytes(
        utf8.encode(body),
        status,
        headers: {'etag': ?etag},
      ),
    );
  }

  void notModified() => handlers.add((_) async => http.Response('', 304));

  void throwError(Object error) => handlers.add((_) async => throw error);

  void hang() => handlers.add(
    (_) => Completer<http.Response>().future, // never answers
  );
}

void main() {
  final catalogBody = sampleText('catalog.json');
  final productsBody = sampleText('products/migros-910.json');

  late _Server server;
  late MemoryCacheStore cache;
  late HttpCatalogRepository repo;
  var now = DateTime.utc(2026, 11, 13, 10);

  setUp(() {
    server = _Server();
    cache = MemoryCacheStore();
    now = DateTime.utc(2026, 11, 13, 10);
    repo = HttpCatalogRepository(
      baseUrl: _base,
      client: server.client,
      cache: cache,
      timeout: const Duration(milliseconds: 100),
      now: () => now,
    );
  });

  Future<CatalogResult> primeCache() async {
    server.respond(catalogBody, etag: '"v1"');
    return repo.loadCatalog();
  }

  group('loadCatalog', () {
    test('first successful load returns network data and caches it', () async {
      final result = await primeCache();

      expect(result.source, CatalogSource.network);
      expect(result.isStale, isFalse);
      expect(result.fetchedAt, now);
      expect(result.catalog, sampleCatalog());
      expect(server.requests.single.url.toString(), '$_base/catalog.json');
      expect(server.requests.single.headers['If-None-Match'], isNull);

      final entry = cache.entries[HttpCatalogRepository.catalogKey]!;
      expect(entry.body, catalogBody);
      expect(entry.etag, '"v1"');
      expect(entry.fetchedAt, now);
    });

    test('304 returns the cached catalog as current', () async {
      await primeCache();
      now = now.add(const Duration(hours: 1));
      server.notModified();

      final result = await repo.loadCatalog();

      expect(server.requests.last.headers['If-None-Match'], '"v1"');
      expect(result.source, CatalogSource.cache);
      expect(result.isStale, isFalse);
      expect(result.fetchedAt, now);
      expect(result.catalog, sampleCatalog());
      expect(cache.entries['catalog.json']!.fetchedAt, now);
    });

    test('forceRefresh sends no If-None-Match', () async {
      await primeCache();
      server.respond(catalogBody, etag: '"v2"');

      await repo.loadCatalog(forceRefresh: true);

      expect(server.requests.last.headers['If-None-Match'], isNull);
      expect(cache.entries['catalog.json']!.etag, '"v2"');
    });

    test('network error falls back to the cache as stale', () async {
      final first = await primeCache();
      now = now.add(const Duration(hours: 5));
      server.throwError(const SocketException('offline'));

      final result = await repo.loadCatalog();

      expect(result.source, CatalogSource.cache);
      expect(result.isStale, isTrue);
      expect(result.fetchedAt, first.fetchedAt);
      expect(result.catalog, first.catalog);
    });

    test('client exception, 5xx and 404 fall back to the cache', () async {
      await primeCache();
      server
        ..throwError(http.ClientException('reset'))
        ..respond('oops', status: 503)
        ..respond('missing', status: 404);
      for (var i = 0; i < 3; i++) {
        final result = await repo.loadCatalog();
        expect(result.isStale, isTrue, reason: 'attempt $i');
      }
    });

    test('timeout falls back to the cache', () async {
      await primeCache();
      server.hang();

      final result = await repo.loadCatalog();

      expect(result.isStale, isTrue);
    });

    test('broken JSON never overwrites the good cache', () async {
      await primeCache();
      server
        ..respond('{"schema_version": 1, "chai', etag: '"bad"')
        ..respond('{"schema_version": 1}', etag: '"bad2"');

      for (var i = 0; i < 2; i++) {
        final result = await repo.loadCatalog();
        expect(result.isStale, isTrue);
        expect(result.catalog, sampleCatalog());
      }
      final entry = cache.entries['catalog.json']!;
      expect(entry.body, catalogBody);
      expect(entry.etag, '"v1"');
    });

    test('no cache and no network throws CatalogUnavailableException', () {
      server.throwError(const SocketException('offline'));
      expect(repo.loadCatalog(), throwsA(isA<CatalogUnavailableException>()));
    });

    test('no cache and broken JSON throws CatalogUnavailableException', () {
      server.respond('<html>captive portal</html>');
      expect(repo.loadCatalog(), throwsA(isA<CatalogUnavailableException>()));
    });

    test('an unreadable cache is not revalidated', () async {
      await cache.write(
        'catalog.json',
        CacheEntry(body: 'garbage', etag: '"v1"', fetchedAt: now),
      );
      server.respond(catalogBody, etag: '"v2"');

      final result = await repo.loadCatalog();

      expect(server.requests.single.headers['If-None-Match'], isNull);
      expect(result.source, CatalogSource.network);
    });
  });

  group('loadProducts', () {
    final migros = sampleCatalog().brochureById('migros-910')!;
    final sok = sampleCatalog().brochureById(
      'sok-2026-11-11-haftanin-firsatlari',
    )!;

    test('fetches, caches, revalidates and falls back', () async {
      server.respond(productsBody, etag: '"p1"');
      final fresh = await repo.loadProducts(migros);
      expect(fresh.products, hasLength(7));
      expect(
        server.requests.single.url.toString(),
        '$_base/products/migros-910.json',
      );
      expect(cache.entries['products/migros-910.json']!.etag, '"p1"');

      server.notModified();
      expect(await repo.loadProducts(migros), fresh);
      expect(server.requests.last.headers['If-None-Match'], '"p1"');

      server.throwError(const SocketException('offline'));
      expect(await repo.loadProducts(migros), fresh);

      server.respond('not json');
      expect(await repo.loadProducts(migros), fresh);
      expect(cache.entries['products/migros-910.json']!.body, productsBody);
    });

    test('offline without cache throws ProductsUnavailableException', () {
      server.throwError(const SocketException('offline'));
      expect(
        repo.loadProducts(migros),
        throwsA(isA<ProductsUnavailableException>()),
      );
    });

    test('page-only brochure throws ProductsUnavailableException', () {
      expect(
        repo.loadProducts(sok),
        throwsA(isA<ProductsUnavailableException>()),
      );
      expect(server.requests, isEmpty);
    });
  });

  group('resolve', () {
    test('relative paths resolve against the catalog folder', () {
      expect(
        repo.resolve('media/sok/x/p01.webp').toString(),
        '$_base/media/sok/x/p01.webp',
      );
      final withSlash = HttpCatalogRepository(
        baseUrl: '$_base/',
        client: server.client,
        cache: cache,
      );
      expect(
        withSlash.resolve('products/a.json').toString(),
        '$_base/products/a.json',
      );
    });

    test('absolute URLs pass through unchanged', () {
      const url =
          'https://cdn1.bim.com.tr/uploads/afisler/3f9c2a7e-51d4-4b8e-9a0c-6e2f1d7b8c41.jpg';
      expect(repo.resolve(url).toString(), url);
      expect(repo.resolve(url).isBundledAsset, isFalse);
    });
  });

  group('FileCacheStore', () {
    late Directory dir;

    setUp(() => dir = Directory.systemTemp.createTempSync('cache_test'));
    tearDown(() => dir.deleteSync(recursive: true));

    test('round-trips, overwrites and tolerates corruption', () async {
      final store = FileCacheStore(directory: () async => dir);
      expect(await store.read('products/a.json'), isNull);

      final t = DateTime.utc(2026, 11, 13, 10);
      await store.write(
        'products/a.json',
        CacheEntry(body: 'one', etag: '"e"', fetchedAt: t),
      );
      await store.write(
        'products/a.json',
        CacheEntry(body: 'two', fetchedAt: t),
      );
      final entry = (await store.read('products/a.json'))!;
      expect(entry.body, 'two');
      expect(entry.etag, isNull);
      expect(entry.fetchedAt, t);

      for (final f in dir.listSync().whereType<File>()) {
        f.writeAsStringSync('{corrupt');
      }
      expect(
        await FileCacheStore(directory: () async => dir)
            .read('products/a.json'),
        isNull,
      );
    });
  });

  group('AssetCatalogRepository', () {
    TestWidgetsFlutterBinding.ensureInitialized();
    final assets = AssetCatalogRepository(rootBundle);

    test('loads the bundled sample', () async {
      final result = await assets.loadCatalog();
      expect(result.source, CatalogSource.bundledSample);
      expect(result.isStale, isFalse);
      expect(result.catalog, sampleCatalog());

      final products = await assets.loadProducts(
        result.catalog.brochureById('bim-2026-11-13-cuma')!,
      );
      expect(products.products, hasLength(14));
    });

    test('relative URLs become asset URIs', () {
      final uri = assets.resolve('media/sok/x/p01.webp');
      expect(uri.isBundledAsset, isTrue);
      expect(uri.assetKey, 'assets/sample/media/sok/x/p01.webp');
      expect(
        assets.resolve('https://a.b/c.jpg').toString(),
        'https://a.b/c.jpg',
      );
    });
  });
}
