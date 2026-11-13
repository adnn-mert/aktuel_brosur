import 'json_reader.dart';

/// How the app shows a chain's brochures.
enum ChainKind {
  /// The scraper collects brochures; show them natively.
  scraped,

  /// The chain's own catalog page is opened in an in-app web view
  /// ([Chain.webUrl]); the catalog lists no brochures for it.
  webview,
}

/// Health of the chain's scraper, as reported by the publisher.
enum ChainStatus {
  /// The last scrape succeeded.
  ok,

  /// The last scrape failed; the brochures shown are the last good copy
  /// (see [Chain.lastOkAt]).
  stale,
}

final RegExp _chainId = RegExp(r'^[a-z0-9_]+$');
final RegExp _hexColor = RegExp(r'^#[0-9A-Fa-f]{6}$');

/// A retail chain (market) such as BİM or A101.
class Chain {
  const Chain({
    required this.id,
    required this.name,
    required this.country,
    required this.kind,
    required this.webUrl,
    required this.status,
    required this.lastOkAt,
    required this.sortOrder,
    this.brandColor,
    this.logoUrl,
  });

  /// Parses one `chains[]` entry.
  ///
  /// Throws [JsonFieldException] for a malformed record or an unknown `kind`;
  /// the catalog parser skips such records. An unknown `status` is read as
  /// [ChainStatus.ok] because status is informational only.
  factory Chain.fromJson(Object? json) {
    final r = JsonReader(json, context: 'chain');
    final id = r.string('id');
    if (!_chainId.hasMatch(id)) {
      throw JsonFieldException('chain.id "$id" is not a valid id');
    }
    final kind = switch (r.string('kind')) {
      'scraped' => ChainKind.scraped,
      'webview' => ChainKind.webview,
      final other => throw JsonFieldException(
        'chain $id: unknown kind "$other"',
      ),
    };
    final status = r.optString('status') == 'stale'
        ? ChainStatus.stale
        : ChainStatus.ok;
    final color = r.raw('brand_color');
    return Chain(
      id: id,
      name: r.nonEmptyString('name'),
      country: r.string('country'),
      kind: kind,
      webUrl: r.nonEmptyString('web_url'),
      status: status,
      lastOkAt: r.optDateTime('last_ok_at'),
      sortOrder: r.integer('sort_order'),
      // A bad colour is cosmetic: drop it rather than the whole chain.
      brandColor: color is String && _hexColor.hasMatch(color)
          ? 0xFF000000 | int.parse(color.substring(1), radix: 16)
          : null,
      logoUrl: r.raw('logo_url') is String ? r.string('logo_url') : null,
    );
  }

  /// Stable id, `^[a-z0-9_]+$` (e.g. `bim`, `a101`, `sok`).
  final String id;

  /// Display name with correct Turkish letters (e.g. `BİM`, `Şok`).
  final String name;

  /// ISO 3166-1 alpha-2 country code (`TR`).
  final String country;

  final ChainKind kind;

  /// The chain's own brochure page (absolute https). For [ChainKind.webview]
  /// chains this is what the web view opens.
  final String webUrl;

  final ChainStatus status;

  /// When the scraper last succeeded for this chain (UTC), if ever.
  final DateTime? lastOkAt;

  /// Publisher-defined position; lower comes first.
  final int sortOrder;

  /// Brand colour as ARGB (`0xFFRRGGBB`), ready for `Color(value)`.
  final int? brandColor;

  /// Logo image, absolute or catalog-relative; resolve before loading.
  final String? logoUrl;

  bool get isWebView => kind == ChainKind.webview;

  bool get isStale => status == ChainStatus.stale;

  @override
  bool operator ==(Object other) =>
      other is Chain &&
      other.id == id &&
      other.name == name &&
      other.country == country &&
      other.kind == kind &&
      other.webUrl == webUrl &&
      other.status == status &&
      other.lastOkAt == lastOkAt &&
      other.sortOrder == sortOrder &&
      other.brandColor == brandColor &&
      other.logoUrl == logoUrl;

  @override
  int get hashCode => Object.hash(
    id,
    name,
    country,
    kind,
    webUrl,
    status,
    lastOkAt,
    sortOrder,
    brandColor,
    logoUrl,
  );

  @override
  String toString() => 'Chain($id)';
}
