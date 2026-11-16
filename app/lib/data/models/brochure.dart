import 'package:flutter/foundation.dart' show listEquals;

import 'json_reader.dart';
import 'media_image.dart';
import 'product.dart';

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

// `relativePath` in schema/catalog.schema.json: no scheme, no leading slash,
// no "..", no whitespace or backslash.
final RegExp _relativePath = RegExp(
  r'^(?![A-Za-z][A-Za-z0-9+.-]*:)(?!/)(?!.*\.\.)[^\s\\]+$',
);

// `ocr_products_url` is optional extra data: a value of the wrong type or
// shape drops the OCR list, never the brochure.
String? _ocrProductsUrl(JsonReader r) {
  final Object? value = r.raw('ocr_products_url');
  if (value is! String || !_relativePath.hasMatch(value)) return null;
  return value;
}

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
    this.ocrProductsUrl,
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
      // OCR products point into the pages; without pages they mean nothing.
      ocrProductsUrl: pages.isEmpty ? null : _ocrProductsUrl(r),
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

  /// Number of products in the written product file (0 for page-only
  /// brochures; OCR products are not counted).
  final int productCount;

  /// Catalog-relative path of the products read from the page images by OCR
  /// (`products_ocr/<id>.json`); non-null iff [hasOcrProducts]. Independent
  /// of [kind] and [productsUrl], which describe the chain's own data only.
  final String? ocrProductsUrl;

  /// Where the scraper found this brochure (the chain's website).
  final String sourceUrl;

  /// When the scraper first saw this brochure (UTC). Drives "new" badges.
  final DateTime firstSeen;

  /// When the brochure's content last changed (UTC).
  final DateTime updatedAt;

  /// True when the page viewer can be opened.
  bool get hasPages => kind != BrochureKind.products && pages.isNotEmpty;

  /// True when the chain's own written product list exists ([productsUrl]).
  /// Does not include OCR products; see [hasProductList].
  bool get hasProducts => kind != BrochureKind.pages && productsUrl != null;

  /// True when products read from the pages by OCR exist ([ocrProductsUrl]).
  bool get hasOcrProducts => ocrProductsUrl != null && hasPages;

  /// True when there is any product list to show: the written one or, failing
  /// that, the OCR one. `CatalogRepository.loadProducts` loads that list.
  bool get hasProductList => hasProducts || hasOcrProducts;

  /// Which list `CatalogRepository.loadProducts` returns: the written one when
  /// both exist, the OCR one otherwise, null when there is none. Lets a
  /// screen show the "broşürden okundu" label before the list has loaded.
  ProductSource? get productListSource => hasProducts
      ? ProductSource.written
      : hasOcrProducts
      ? ProductSource.ocr
      : null;

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
      other.ocrProductsUrl == ocrProductsUrl &&
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
    ocrProductsUrl,
    sourceUrl,
    firstSeen,
    updatedAt,
  );

  @override
  String toString() => 'Brochure($id)';
}
