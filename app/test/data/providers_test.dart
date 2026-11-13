import 'dart:async';

import 'package:aktuel_brosur/data/data.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../helpers.dart';

/// Repository whose answers are scripted per call.
class _FakeRepository implements CatalogRepository {
  final List<FutureOr<CatalogResult> Function()> answers = [];
  int catalogCalls = 0;
  final Map<String, ProductFile> products = {};

  void succeed(CatalogResult result) => answers.add(() => result);

  void throwError(Object error) => answers.add(() => throw error);

  @override
  Future<CatalogResult> loadCatalog({bool forceRefresh = false}) async {
    catalogCalls++;
    return answers.removeAt(0)();
  }

  @override
  Future<ProductFile> loadProducts(Brochure brochure) async {
    final file = products[brochure.id];
    if (file == null) throw ProductsUnavailableException(brochure.id);
    return file;
  }

  @override
  Uri resolve(String url) => Uri.parse('https://test/').resolve(url);
}

CatalogResult _result(
  Catalog catalog, {
  bool stale = false,
  CatalogSource source = CatalogSource.network,
}) => CatalogResult(
  catalog: catalog,
  source: source,
  fetchedAt: DateTime.utc(2026, 11, 13, 10),
  isStale: stale,
);

Catalog _catalogWith({int minAppVersion = 1}) {
  final base = sampleCatalog();
  return Catalog(
    schemaVersion: 1,
    generatedAt: DateTime.utc(2026, 11, 14),
    minAppVersion: minAppVersion,
    chains: base.chains,
    brochures: base.brochures.take(2).toList(),
  );
}

void main() {
  late _FakeRepository repo;
  late MemoryFavoritesStore favorites;

  ProviderContainer makeContainer() => ProviderContainer.test(
    overrides: [
      catalogRepositoryProvider.overrideWithValue(repo),
      favoritesStoreProvider.overrideWithValue(favorites),
      clockProvider.overrideWithValue(Clock.fixed(DateTime(2026, 11, 13, 15))),
    ],
  );

  setUp(() {
    repo = _FakeRepository();
    favorites = MemoryFavoritesStore();
  });

  group('catalogProvider', () {
    test('loads on first read', () async {
      repo.succeed(_result(sampleCatalog()));
      final container = makeContainer();

      expect(container.read(catalogProvider).isLoading, isTrue);
      final result = await container.read(catalogProvider.future);

      expect(result.catalog, sampleCatalog());
      expect(container.read(catalogProvider).value, result);
    });

    test('refresh replaces the data and reports the outcome', () async {
      repo
        ..succeed(_result(sampleCatalog()))
        ..succeed(_result(_catalogWith()))
        ..succeed(_result(_catalogWith(), stale: true));
      final container = makeContainer();
      await container.read(catalogProvider.future);
      final notifier = container.read(catalogProvider.notifier);

      expect(await notifier.refresh(), RefreshOutcome.updated);
      expect(
        container.read(catalogProvider).value!.catalog.brochures,
        hasLength(2),
      );

      expect(await notifier.refresh(), RefreshOutcome.offline);
      expect(container.read(catalogProvider).value!.isStale, isTrue);
    });

    test('failed refresh keeps the previous data', () async {
      final first = _result(sampleCatalog());
      repo
        ..succeed(first)
        ..throwError(const CatalogUnavailableException('offline'));
      final container = makeContainer();
      await container.read(catalogProvider.future);

      final outcome = await container.read(catalogProvider.notifier).refresh();

      expect(outcome, RefreshOutcome.failed);
      final state = container.read(catalogProvider);
      expect(state.hasError, isFalse);
      expect(state.value, first);
    });

    test('concurrent refreshes share one download', () async {
      repo
        ..succeed(_result(sampleCatalog()))
        ..succeed(_result(_catalogWith()));
      final container = makeContainer();
      await container.read(catalogProvider.future);
      final notifier = container.read(catalogProvider.notifier);

      await Future.wait([notifier.refresh(), notifier.refresh()]);

      expect(repo.catalogCalls, 2);
    });

    test('first load failure is an error; refresh recovers', () async {
      repo
        ..throwError(const CatalogUnavailableException('offline'))
        ..succeed(_result(sampleCatalog()));
      final container = makeContainer();
      container.listen(catalogProvider, (_, _) {});

      await expectLater(
        container.read(catalogProvider.future),
        throwsA(isA<CatalogUnavailableException>()),
      );
      expect(container.read(catalogProvider).hasError, isTrue);
      // Derived providers mirror the error.
      expect(container.read(orderedChainsProvider).hasError, isTrue);

      final outcome = await container.read(catalogProvider.notifier).refresh();

      expect(outcome, RefreshOutcome.updated);
      expect(container.read(catalogProvider).value!.catalog, sampleCatalog());
    });
  });

  group('derived providers', () {
    setUp(() => repo.succeed(_result(sampleCatalog())));

    test('orderedChainsProvider puts favourites first', () async {
      favorites = MemoryFavoritesStore(['gratis']);
      final container = makeContainer();
      container.listen(orderedChainsProvider, (_, _) {});
      await container.read(catalogProvider.future);
      await container.read(favoritesProvider.future);

      final ids = container.read(orderedChainsProvider).value!.map((c) => c.id);
      expect(ids, [
        'gratis',
        'bim',
        'a101',
        'sok',
        'migros',
        'watsons',
        'carrefoursa',
      ]);
    });

    test('chain, summary, groups and brochure lookups', () async {
      final container = makeContainer();
      await container.read(catalogProvider.future);

      expect(container.read(chainProvider('sok')).value!.name, 'Şok');
      expect(container.read(chainProvider('nope')).value, isNull);

      final summary = container.read(chainSummaryProvider('bim')).value!;
      expect(summary.currentCount, 1);
      expect(summary.isNew, isTrue);
      expect(container.read(chainSummaryProvider('nope')).value, isNull);

      final groups = container.read(brochureGroupsProvider('bim')).value!;
      expect(groups.current.single.id, 'bim-2026-11-13-cuma');
      expect(groups.upcoming.single.id, 'bim-2026-11-18-carsamba');
      expect(groups.past.single.id, 'bim-2026-11-03-sali');

      expect(
        container.read(brochureProvider('migros-910')).value!.kind,
        BrochureKind.products,
      );
      expect(container.read(brochureProvider('gone')).value, isNull);
      expect(container.read(appUpdateRequiredProvider), isFalse);
    });

    test('productsProvider loads through the repository', () async {
      final file = ProductFile.parse(sampleText('products/migros-910.json'));
      repo.products['migros-910'] = file;
      final container = makeContainer();
      container
        ..listen(productsProvider('migros-910'), (_, _) {})
        ..listen(productsProvider('bim-2026-11-18-carsamba'), (_, _) {});

      expect(await container.read(productsProvider('migros-910').future), file);
      await expectLater(
        container.read(productsProvider('bim-2026-11-18-carsamba').future),
        throwsA(isA<ProductsUnavailableException>()),
      );
    });
  });

  test('appUpdateRequiredProvider compares min_app_version', () async {
    repo.succeed(_result(_catalogWith(minAppVersion: appDataVersion + 1)));
    final container = makeContainer();
    await container.read(catalogProvider.future);
    expect(container.read(appUpdateRequiredProvider), isTrue);
  });

  group('favoritesProvider', () {
    test('toggle adds and removes', () async {
      final container = makeContainer();
      container.listen(favoritesProvider, (_, _) {});
      expect(await container.read(favoritesProvider.future), isEmpty);
      final notifier = container.read(favoritesProvider.notifier);

      expect(await notifier.toggle('bim'), isTrue);
      expect(container.read(favoritesProvider).value, {'bim'});
      expect(container.read(isFavoriteProvider('bim')), isTrue);
      expect(favorites.ids, {'bim'});

      await notifier.toggle('bim');
      expect(container.read(favoritesProvider).value, isEmpty);
      expect(container.read(isFavoriteProvider('bim')), isFalse);
    });

    test('toggle persists in shared_preferences across restarts', () async {
      TestWidgetsFlutterBinding.ensureInitialized();
      SharedPreferences.setMockInitialValues({});
      ProviderContainer withPrefs() => ProviderContainer.test(
        overrides: [
          favoritesStoreProvider.overrideWithValue(PrefsFavoritesStore()),
        ],
      );

      final first = withPrefs();
      await first.read(favoritesProvider.future);
      await first.read(favoritesProvider.notifier).toggle('sok');
      await first.read(favoritesProvider.notifier).toggle('bim');
      first.dispose();

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getStringList(PrefsFavoritesStore.key), ['bim', 'sok']);

      final second = withPrefs();
      expect(await second.read(favoritesProvider.future), {'bim', 'sok'});
      await second.read(favoritesProvider.notifier).toggle('sok');
      expect(prefs.getStringList(PrefsFavoritesStore.key), ['bim']);
    });
  });
}
