import 'dart:convert';

import 'package:flutter/foundation.dart' show listEquals;

import '../errors.dart';
import 'brochure.dart';
import 'chain.dart';
import 'json_reader.dart';

/// The whole published `catalog.json`: every chain and every brochure.
class Catalog {
  Catalog({
    required this.schemaVersion,
    required this.generatedAt,
    required this.minAppVersion,
    required List<Chain> chains,
    required List<Brochure> brochures,
    this.skippedChainCount = 0,
    this.skippedBrochureCount = 0,
  }) : chains = List.unmodifiable(chains),
       brochures = List.unmodifiable(brochures),
       _chainsById = {for (final c in chains) c.id: c},
       _brochuresById = {for (final b in brochures) b.id: b};

  /// Parses decoded JSON.
  ///
  /// Broken or unknown-kind chain/brochure records are skipped and counted
  /// ([skippedCount]); so are brochures whose chain is missing and duplicate
  /// ids. Throws [CatalogFormatException] only when the root itself is bad.
  factory Catalog.fromJson(Object? json) {
    final JsonReader root;
    final int schemaVersion;
    final DateTime generatedAt;
    final int minAppVersion;
    final List<dynamic> rawChains;
    final List<dynamic> rawBrochures;
    try {
      root = JsonReader(json, context: 'catalog');
      schemaVersion = root.integer('schema_version');
      generatedAt = root.dateTime('generated_at');
      minAppVersion = root.integer('min_app_version');
      rawChains = root.list('chains');
      rawBrochures = root.list('brochures');
    } on JsonFieldException catch (e) {
      throw CatalogFormatException(e.message, e);
    }
    if (schemaVersion < 1 || minAppVersion < 1) {
      throw const CatalogFormatException(
        'schema_version and min_app_version must be >= 1',
      );
    }

    final chains = <String, Chain>{};
    var skippedChains = 0;
    for (final raw in rawChains) {
      try {
        final chain = Chain.fromJson(raw);
        if (chains.containsKey(chain.id)) {
          skippedChains++;
        } else {
          chains[chain.id] = chain;
        }
      } on JsonFieldException {
        skippedChains++;
      }
    }

    final brochures = <String, Brochure>{};
    var skippedBrochures = 0;
    for (final raw in rawBrochures) {
      try {
        final brochure = Brochure.fromJson(raw);
        if (!chains.containsKey(brochure.chainId) ||
            brochures.containsKey(brochure.id)) {
          skippedBrochures++;
        } else {
          brochures[brochure.id] = brochure;
        }
      } on JsonFieldException {
        skippedBrochures++;
      }
    }

    return Catalog(
      schemaVersion: schemaVersion,
      generatedAt: generatedAt,
      minAppVersion: minAppVersion,
      chains: chains.values.toList(),
      brochures: brochures.values.toList(),
      skippedChainCount: skippedChains,
      skippedBrochureCount: skippedBrochures,
    );
  }

  /// Parses the raw `catalog.json` text. Throws [CatalogFormatException] if it
  /// is not JSON or its root is unusable.
  factory Catalog.parse(String body) {
    final Object? decoded;
    try {
      decoded = jsonDecode(body);
    } on FormatException catch (e) {
      throw CatalogFormatException('catalog.json is not valid JSON', e);
    }
    return Catalog.fromJson(decoded);
  }

  final int schemaVersion;

  /// When the scraper published this catalog (UTC).
  final DateTime generatedAt;

  /// Oldest app data version able to read this catalog; see
  /// `appUpdateRequiredProvider`.
  final int minAppVersion;

  /// All usable chains, in publisher order (use `orderChains` to sort).
  final List<Chain> chains;

  /// All usable brochures of all chains.
  final List<Brochure> brochures;

  final int skippedChainCount;
  final int skippedBrochureCount;

  final Map<String, Chain> _chainsById;
  final Map<String, Brochure> _brochuresById;

  /// Records dropped while parsing (malformed, unknown kind, orphaned or
  /// duplicate). Non-zero usually means the app is older than the data.
  int get skippedCount => skippedChainCount + skippedBrochureCount;

  Chain? chainById(String id) => _chainsById[id];

  Brochure? brochureById(String id) => _brochuresById[id];

  List<Brochure> brochuresOf(String chainId) =>
      brochures.where((b) => b.chainId == chainId).toList();

  @override
  bool operator ==(Object other) =>
      other is Catalog &&
      other.schemaVersion == schemaVersion &&
      other.generatedAt == generatedAt &&
      other.minAppVersion == minAppVersion &&
      listEquals(other.chains, chains) &&
      listEquals(other.brochures, brochures) &&
      other.skippedChainCount == skippedChainCount &&
      other.skippedBrochureCount == skippedBrochureCount;

  @override
  int get hashCode => Object.hash(
    schemaVersion,
    generatedAt,
    minAppVersion,
    Object.hashAll(chains),
    Object.hashAll(brochures),
    skippedChainCount,
    skippedBrochureCount,
  );

  @override
  String toString() =>
      'Catalog(${chains.length} chains, ${brochures.length} brochures, '
      'skipped $skippedCount)';
}
