/// Riverpod providers: the only way screens reach data.
///
/// Catalog-derived providers return `AsyncValue<T>` that mirror
/// [catalogProvider]: loading on first launch, error when nothing could be
/// loaded, data otherwise (data is kept while a refresh is running or after a
/// refresh failed). See `README.md` in this folder for per-screen usage.
library;

import 'package:flutter/services.dart' show rootBundle;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import 'brochure_grouping.dart';
import 'cache_store.dart';
import 'catalog_repository.dart';
import 'errors.dart';
import 'favorites_store.dart';
import 'models/brochure.dart';
import 'models/chain.dart';
import 'models/product.dart';

/// Data format version this build understands. A catalog whose
/// `min_app_version` is higher means "this app is too old"
/// ([appUpdateRequiredProvider]).
const int appDataVersion = 1;

/// Base URL of the published data (the folder holding `catalog.json`), from
/// `--dart-define=CATALOG_BASE_URL=https://...`. Empty means "use the bundled
/// sample data".
const String catalogBaseUrlFromEnvironment = String.fromEnvironment(
  'CATALOG_BASE_URL',
);

// Riverpod 3 retries failed providers automatically; for data that failed
// because the phone is offline that only burns battery. The UI offers an
// explicit retry instead.
Duration? _noRetry(int retryCount, Object error) => null;

/// Source of "now"; override with [Clock.fixed] in tests.
class Clock {
  const Clock();

  const factory Clock.fixed(DateTime now) = _FixedClock;

  DateTime now() => DateTime.now();

  /// Today's calendar day (local midnight).
  DateTime today() => dateOnly(now());
}

class _FixedClock extends Clock {
  const _FixedClock(this._now);

  final DateTime _now;

  @override
  DateTime now() => _now;
}

/// Current time source. Derived providers read `today()` from it when they
/// rebuild; call `ref.invalidate(clockProvider)` (e.g. when the app resumes
/// on a new day) to regroup brochures.
final clockProvider = Provider<Clock>((ref) => const Clock());

/// See [catalogBaseUrlFromEnvironment].
final catalogBaseUrlProvider = Provider<String>(
  (ref) => catalogBaseUrlFromEnvironment,
);

/// Shared HTTP client, closed with the container.
final httpClientProvider = Provider<http.Client>((ref) {
  final client = http.Client();
  ref.onDispose(client.close);
  return client;
});

/// On-disk store for the offline copies of `catalog.json` and product files.
final cacheStoreProvider = Provider<CacheStore>((ref) => FileCacheStore());

/// The repository in use: [HttpCatalogRepository] when a base URL is
/// configured, otherwise [AssetCatalogRepository] with the bundled sample.
/// Screens normally do not need it except for [CatalogRepository.resolve].
final catalogRepositoryProvider = Provider<CatalogRepository>((ref) {
  final baseUrl = ref.watch(catalogBaseUrlProvider).trim();
  if (baseUrl.isEmpty) return AssetCatalogRepository(rootBundle);
  return HttpCatalogRepository(
    baseUrl: baseUrl,
    client: ref.watch(httpClientProvider),
    cache: ref.watch(cacheStoreProvider),
  );
});

/// Result of [CatalogNotifier.refresh], for a "pull to refresh" message.
enum RefreshOutcome {
  /// Fresh data from the server (or the server confirmed ours is current).
  updated,

  /// The server was unreachable; the cached copy is shown (`isStale`).
  offline,

  /// Nothing could be loaded. Earlier data, if any, is still shown.
  failed,
}

/// Loads the catalog once and refreshes it on demand.
class CatalogNotifier extends AsyncNotifier<CatalogResult> {
  Future<RefreshOutcome>? _inFlight;

  @override
  Future<CatalogResult> build() =>
      ref.watch(catalogRepositoryProvider).loadCatalog();

  /// Downloads the catalog again. Never throws.
  ///
  /// While it runs, existing data stays in [state] (no loading flash); with
  /// no data yet (after a failed first load) [state] becomes loading. On
  /// failure existing data is kept and [RefreshOutcome.failed] is returned;
  /// without existing data [state] becomes the error. Concurrent calls share
  /// one download.
  Future<RefreshOutcome> refresh() =>
      _inFlight ??= _refresh().whenComplete(() => _inFlight = null);

  Future<RefreshOutcome> _refresh() async {
    final repository = ref.read(catalogRepositoryProvider);
    if (!state.hasValue) state = const AsyncLoading();
    try {
      final result = await repository.loadCatalog(forceRefresh: true);
      if (ref.mounted) state = AsyncData(result);
      return result.isStale ? RefreshOutcome.offline : RefreshOutcome.updated;
    } on Object catch (error, stack) {
      if (ref.mounted && !state.hasValue) state = AsyncError(error, stack);
      return RefreshOutcome.failed;
    }
  }
}

/// The catalog with its freshness ([CatalogResult.isStale],
/// [CatalogResult.source]). Errors are [CatalogUnavailableException] (offline
/// on first launch) or [CatalogFormatException] (published file broken and
/// nothing cached).
final catalogProvider = AsyncNotifierProvider<CatalogNotifier, CatalogResult>(
  CatalogNotifier.new,
  retry: _noRetry,
);

/// Where favourites are stored.
final favoritesStoreProvider = Provider<FavoritesStore>(
  (ref) => PrefsFavoritesStore(),
);

/// Favourite chain ids. Loading only for a moment at startup.
class FavoritesNotifier extends AsyncNotifier<Set<String>> {
  @override
  Future<Set<String>> build() => ref.watch(favoritesStoreProvider).read();

  /// Adds or removes [chainId]. The new state shows immediately; if saving
  /// fails the change is rolled back and `false` is returned. Never throws.
  Future<bool> toggle(String chainId) async {
    final store = ref.read(favoritesStoreProvider);
    final Set<String> before;
    try {
      before = state.value ?? await future;
    } on Object {
      return false;
    }
    final adding = !before.contains(chainId);
    state = AsyncData(
      Set.unmodifiable(
        adding ? {...before, chainId} : ({...before}..remove(chainId)),
      ),
    );
    try {
      final saved = adding
          ? await store.add(chainId)
          : await store.remove(chainId);
      if (ref.mounted) state = AsyncData(saved);
      return true;
    } on Object {
      if (ref.mounted) state = AsyncData(before);
      return false;
    }
  }
}

/// Favourite chain ids; mutate with
/// `ref.read(favoritesProvider.notifier).toggle(id)`.
final favoritesProvider = AsyncNotifierProvider<FavoritesNotifier, Set<String>>(
  FavoritesNotifier.new,
  retry: _noRetry,
);

/// Whether [chainId] is a favourite (false while favourites load).
final isFavoriteProvider = Provider.family<bool, String>(
  (ref, chainId) =>
      ref.watch(favoritesProvider).value?.contains(chainId) ?? false,
);

/// Home screen: every chain, favourites first, then `sort_order`, then name.
/// Includes web-view chains (check `Chain.isWebView`).
final orderedChainsProvider = Provider<AsyncValue<List<Chain>>>((ref) {
  final catalog = ref.watch(catalogProvider);
  final favorites = ref.watch(favoritesProvider);
  // Wait for favourites so the grid does not reshuffle a moment after it
  // appears. A favourites read error just means "no favourites".
  if (catalog.hasValue && favorites.isLoading && !favorites.hasValue) {
    return const AsyncLoading();
  }
  final ids = favorites.value ?? const <String>{};
  return catalog.whenData((r) => orderChains(r.catalog.chains, ids));
});

/// One chain by id; data is null if the id is unknown.
final chainProvider = Provider.family<AsyncValue<Chain?>, String>(
  (ref, chainId) =>
      ref.watch(catalogProvider).whenData((r) => r.catalog.chainById(chainId)),
);

/// Home-screen card data for one chain; data is null if the id is unknown.
final chainSummaryProvider = Provider.family<AsyncValue<ChainSummary?>, String>(
  (ref, chainId) {
    final today = ref.watch(clockProvider).today();
    return ref.watch(catalogProvider).whenData((r) {
      final chain = r.catalog.chainById(chainId);
      if (chain == null) return null;
      return chainSummary(chain, r.catalog.brochuresOf(chainId), today);
    });
  },
);

/// Market screen: the chain's brochures as "Bu hafta" ([BrochureGroups.current]),
/// "Gelecek hafta" ([BrochureGroups.upcoming]) and "Geçmiş"
/// ([BrochureGroups.past]). Empty groups for an unknown chain.
final brochureGroupsProvider =
    Provider.family<AsyncValue<BrochureGroups>, String>((ref, chainId) {
      final today = ref.watch(clockProvider).today();
      return ref
          .watch(catalogProvider)
          .whenData(
            (r) => groupBrochures(r.catalog.brochuresOf(chainId), today),
          );
    });

/// One brochure by id (viewer screen); data is null if the id is unknown,
/// e.g. it expired and the publisher removed it.
final brochureProvider = Provider.family<AsyncValue<Brochure?>, String>(
  (ref, brochureId) => ref
      .watch(catalogProvider)
      .whenData((r) => r.catalog.brochureById(brochureId)),
);

/// Product list of one brochure. Fetched when first watched, cached on disk,
/// released when no screen watches it. Errors are
/// [ProductsUnavailableException] or [CatalogFormatException];
/// `ref.invalidate(productsProvider(id))` retries.
final productsProvider = FutureProvider.autoDispose.family<ProductFile, String>(
  (ref, brochureId) async {
    final repository = ref.watch(catalogRepositoryProvider);
    final result = await ref.watch(catalogProvider.future);
    final brochure = result.catalog.brochureById(brochureId);
    if (brochure == null) {
      throw ProductsUnavailableException('unknown brochure $brochureId');
    }
    return repository.loadProducts(brochure);
  },
  retry: _noRetry,
);

/// True when the published data needs a newer app (`min_app_version` above
/// [appDataVersion]). Show an "update the app" notice; the data may still
/// partly display.
final appUpdateRequiredProvider = Provider<bool>((ref) {
  final minVersion = ref.watch(catalogProvider).value?.catalog.minAppVersion;
  return minVersion != null && minVersion > appDataVersion;
});
