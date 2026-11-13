import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';

/// One cached HTTP body plus what is needed to revalidate it.
class CacheEntry {
  const CacheEntry({required this.body, required this.fetchedAt, this.etag});

  final String body;

  /// The server's `ETag`, sent back as `If-None-Match`.
  final String? etag;

  /// When the body was last confirmed current by the server (UTC).
  final DateTime fetchedAt;

  CacheEntry copyWith({DateTime? fetchedAt}) => CacheEntry(
    body: body,
    etag: etag,
    fetchedAt: fetchedAt ?? this.fetchedAt,
  );
}

/// Key/value storage for downloaded JSON. Keys look like `catalog.json` or
/// `products/<brochure_id>.json`.
///
/// Implementations must make [write] all-or-nothing so a crash mid-write
/// never leaves a half-written body behind.
abstract interface class CacheStore {
  Future<CacheEntry?> read(String key);

  Future<void> write(String key, CacheEntry entry);
}

/// In-memory store, for tests and as a last resort when no disk is available.
class MemoryCacheStore implements CacheStore {
  final Map<String, CacheEntry> entries = {};

  @override
  Future<CacheEntry?> read(String key) async => entries[key];

  @override
  Future<void> write(String key, CacheEntry entry) async {
    entries[key] = entry;
  }
}

/// Stores entries as files under the app support directory (not the cache
/// directory: the OS may purge that, and this is our offline copy).
class FileCacheStore implements CacheStore {
  /// [directory] overrides the default location (used by tests).
  FileCacheStore({Future<Directory> Function()? directory})
    : _directory = directory ?? _defaultDirectory;

  final Future<Directory> Function() _directory;
  Directory? _resolved;

  static Future<Directory> _defaultDirectory() async {
    final support = await getApplicationSupportDirectory();
    return Directory('${support.path}${Platform.pathSeparator}catalog_cache');
  }

  Future<File> _file(String key) async {
    final dir = _resolved ??= await _directory();
    // Flatten keys so `products/x.json` needs no sub-directories.
    final safe = key.replaceAll(RegExp(r'[^A-Za-z0-9._-]'), '__');
    return File('${dir.path}${Platform.pathSeparator}$safe');
  }

  @override
  Future<CacheEntry?> read(String key) async {
    try {
      final file = await _file(key);
      if (!await file.exists()) return null;
      final json = jsonDecode(await file.readAsString());
      if (json is! Map<String, dynamic>) return null;
      final body = json['body'];
      final fetchedAt = DateTime.tryParse('${json['fetched_at']}');
      final etag = json['etag'];
      if (body is! String || fetchedAt == null) return null;
      return CacheEntry(
        body: body,
        etag: etag is String ? etag : null,
        fetchedAt: fetchedAt.toUtc(),
      );
    } on Object {
      // A corrupt cache file behaves like a missing one.
      return null;
    }
  }

  @override
  Future<void> write(String key, CacheEntry entry) async {
    final file = await _file(key);
    await file.parent.create(recursive: true);
    final tmp = File('${file.path}.tmp');
    await tmp.writeAsString(
      jsonEncode({
        'body': entry.body,
        'etag': entry.etag,
        'fetched_at': entry.fetchedAt.toUtc().toIso8601String(),
      }),
      flush: true,
    );
    // rename is atomic on the same volume: readers see old or new, never half.
    await tmp.rename(file.path);
  }
}
