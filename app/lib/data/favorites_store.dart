import 'package:shared_preferences/shared_preferences.dart';

/// Persists the set of favourite chain ids.
abstract interface class FavoritesStore {
  Future<Set<String>> read();

  /// Adds [chainId] and returns the new set.
  Future<Set<String>> add(String chainId);

  /// Removes [chainId] and returns the new set.
  Future<Set<String>> remove(String chainId);
}

/// [FavoritesStore] on top of `shared_preferences`.
class PrefsFavoritesStore implements FavoritesStore {
  PrefsFavoritesStore({Future<SharedPreferences> Function()? prefs})
    : _prefs = prefs ?? SharedPreferences.getInstance;

  static const String key = 'favorite_chain_ids';

  final Future<SharedPreferences> Function() _prefs;

  @override
  Future<Set<String>> read() async {
    final prefs = await _prefs();
    return Set.unmodifiable(prefs.getStringList(key) ?? const <String>[]);
  }

  @override
  Future<Set<String>> add(String chainId) => _update((ids) => ids.add(chainId));

  @override
  Future<Set<String>> remove(String chainId) =>
      _update((ids) => ids.remove(chainId));

  Future<Set<String>> _update(void Function(Set<String> ids) change) async {
    final prefs = await _prefs();
    final ids = {...?prefs.getStringList(key)};
    change(ids);
    // Sorted so the stored value is deterministic.
    await prefs.setStringList(key, ids.toList()..sort());
    return Set.unmodifiable(ids);
  }
}

/// In-memory [FavoritesStore] for tests and previews.
class MemoryFavoritesStore implements FavoritesStore {
  MemoryFavoritesStore([Iterable<String> initial = const []])
    : ids = {...initial};

  final Set<String> ids;

  @override
  Future<Set<String>> read() async => Set.unmodifiable(ids);

  @override
  Future<Set<String>> add(String chainId) async {
    ids.add(chainId);
    return Set.unmodifiable(ids);
  }

  @override
  Future<Set<String>> remove(String chainId) async {
    ids.remove(chainId);
    return Set.unmodifiable(ids);
  }
}
