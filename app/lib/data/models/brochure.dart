import 'package:flutter/foundation.dart' show listEquals;

import 'json_reader.dart';
import 'media_image.dart';

/// What a brochure contains.
enum BrochureKind {
  /// Page images only (open the page viewer).
  pages,

  /// A priced product list only (open the product list).
  products,

  /// Both page images and a product list (e.g. BİM).
  both,
}

final RegExp _brochureId = RegExp(r'^[a-z0-9_-]+$');

/// One brochure (a weekly flyer, a "Cuma" poster set, a monthly catalog...).
class Brochure {
  const Brochure({
    required this.id,
    required this.chainId,
    required this.title,
    required this.dateLabel,
    required this.validFrom,
    required this.validTo,
    required this.kind,
    required this.cover,
    required this.pages,
    required this.productsUrl,
    required this.productCount,
    required this.sourceUrl,
    required this.firstSeen,
    required this.updatedAt,
  });

  /// Parses one `brochures[]` entry.
  ///
  /// Throws [JsonFieldException] for a malformed or self-contradictory record
  /// (unknown `kind`, a page brochure without pages, `valid_from` after
  /// `valid_to`...); the catalog parser skips such records.
  factory Brochure.fromJson(Object? json) {
    final r = JsonReader(json, context: 'brochure');
    final id = r.string('id');
    if (!_brochureId.hasMatch(id)) {
      throw JsonFieldException('brochure.id "$id" is not a valid id');
    }
    final kind = switch (r.string('kind')) {
      'pages' => BrochureKind.pages,
      'products' => BrochureKind.products,
      'both' => BrochureKind.both,
      final other => throw JsonFieldException(
        'brochure $id: unknown kind "$other"',
      ),
    };
    final pages = [
      for (final (i, page) in r.list('pages').indexed)
        MediaImage.fromJson(page, context: 'brochure $id page $i'),
    ];
    final coverJson = r.raw('cover');
    final validFrom = r.optDate('valid_from');
    final validTo = r.optDate('valid_to');
    final productsUrl = r.optString('products_url');

    if (kind != BrochureKind.products && pages.isEmpty) {
      throw JsonFieldException('brochure $id: kind $kind needs pages');
    }
    if (kind != BrochureKind.pages && (productsUrl ?? '').isEmpty) {
      throw JsonFieldException('brochure $id: kind $kind needs products_url');
    }
    if (validFrom != null && validTo != null && validFrom.isAfter(validTo)) {
      throw JsonFieldException('brochure $id: valid_from after valid_to');
    }

    return Brochure(
      id: id,
      chainId: r.string('chain_id'),
      title: r.nonEmptyString('title'),
      dateLabel: r.optString('date_label'),
      validFrom: validFrom,
      validTo: validTo,
      kind: kind,
      cover: coverJson == null
          ? null
          : MediaImage.fromJson(coverJson, context: 'brochure $id cover'),
      pages: List.unmodifiable(pages),
      productsUrl: kind == BrochureKind.pages ? null : productsUrl,
      productCount: r.optInteger('product_count') ?? 0,
      sourceUrl: r.nonEmptyString('source_url'),
      firstSeen: r.dateTime('first_seen'),
      updatedAt: r.dateTime('updated_at'),
    );
  }

  /// Stable id, `^[a-z0-9_-]+$`.
  final String id;

  final String chainId;

  /// Title as the chain printed it (e.g. "Haftanın Fırsatları").
  final String title;

  /// The chain's own date text (e.g. "13 Kasım Cuma"), shown when no
  /// structured dates exist. Prefer `formatBrochureDates` for display.
  final String? dateLabel;

  /// First valid day, local midnight (date only). Null when unknown.
  final DateTime? validFrom;

  /// Last valid day (inclusive), local midnight. Null when unknown/open.
  final DateTime? validTo;

  final BrochureKind kind;

  /// Thumbnail for lists. May be null; fall back to `pages.first`.
  final MediaImage? cover;

  /// Page images in reading order. Non-empty unless [kind] is `products`.
  final List<MediaImage> pages;

  /// Catalog-relative path of the product file; non-null iff [hasProducts].
  final String? productsUrl;

  /// Number of products in the product file (0 for page-only brochures).
  final int productCount;

  /// Where the scraper found this brochure (the chain's website).
  final String sourceUrl;

  /// When the scraper first saw this brochure (UTC). Drives "new" badges.
  final DateTime firstSeen;

  /// When the brochure's content last changed (UTC).
  final DateTime updatedAt;

  /// True when the page viewer can be opened.
  bool get hasPages => kind != BrochureKind.products && pages.isNotEmpty;

  /// True when the product list can be opened.
  bool get hasProducts => kind != BrochureKind.pages && productsUrl != null;

  /// Best image for a thumbnail: [cover], else the first page, else null.
  MediaImage? get thumbnail => cover ?? (pages.isEmpty ? null : pages.first);

  @override
  bool operator ==(Object other) =>
      other is Brochure &&
      other.id == id &&
      other.chainId == chainId &&
      other.title == title &&
      other.dateLabel == dateLabel &&
      other.validFrom == validFrom &&
      other.validTo == validTo &&
      other.kind == kind &&
      other.cover == cover &&
      listEquals(other.pages, pages) &&
      other.productsUrl == productsUrl &&
      other.productCount == productCount &&
      other.sourceUrl == sourceUrl &&
      other.firstSeen == firstSeen &&
      other.updatedAt == updatedAt;

  @override
  int get hashCode => Object.hash(
    id,
    chainId,
    title,
    dateLabel,
    validFrom,
    validTo,
    kind,
    cover,
    Object.hashAll(pages),
    productsUrl,
    productCount,
    sourceUrl,
    firstSeen,
    updatedAt,
  );

  @override
  String toString() => 'Brochure($id)';
}
