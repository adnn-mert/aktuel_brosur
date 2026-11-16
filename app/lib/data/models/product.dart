import 'dart:convert';

import 'package:flutter/foundation.dart' show listEquals;

import '../errors.dart';
import 'json_reader.dart';
import 'money.dart';

/// Where a product's price comes from.
enum ProductSource {
  /// The chain's own written product list (BİM, Migros...).
  written,

  /// Read from a brochure page image by a vision model ("broşürden okundu").
  /// [Product.pageIndex] then names the page that prints it.
  ocr,
}

/// One priced product as the chain printed it.
class Product {
  const Product({
    required this.name,
    required this.price,
    this.brand,
    this.quantityText,
    this.oldPrice,
    this.image,
    this.pageIndex,
    this.sourceUrl,
    this.source = ProductSource.written,
    Money? memberPrice,
    String? memberPriceLabel,
  }) : memberPrice = memberPriceLabel == null ? null : memberPrice,
       memberPriceLabel = memberPrice == null ? null : memberPriceLabel;

  /// Throws [JsonFieldException] for a malformed record; the product file
  /// parser skips it.
  ///
  /// [ocrFile] is true for a file published as OCR output
  /// (`ocr_products_url`): every product in it is OCR whatever its own
  /// `source` says, so a record that forgot the field is never shown as the
  /// chain's written price.
  ///
  /// An OCR product must name its page (`page_index` >= 0): its price is only
  /// trustworthy next to the page it was read from. A `source` value this
  /// build does not know is rejected rather than taken as written: it marks a
  /// price that is not from the chain's own list, and showing it without the
  /// right label is exactly what the separate OCR file exists to prevent.
  factory Product.fromJson(
    Object? json, {
    String currency = 'TRY',
    bool ocrFile = false,
  }) {
    final r = JsonReader(json, context: 'product');
    final price = r.integer('price_minor');
    final oldPrice = r.optInteger('old_price_minor');
    final pageIndex = r.optInteger('page_index');
    if (price < 0 || (oldPrice != null && oldPrice < 0)) {
      throw const JsonFieldException('product: negative price');
    }
    final source = switch (r.optString('source')) {
      null => ocrFile ? ProductSource.ocr : ProductSource.written,
      'ocr' => ProductSource.ocr,
      final other => throw JsonFieldException(
        'product: unknown source "$other"',
      ),
    };
    if (source == ProductSource.ocr && (pageIndex == null || pageIndex < 0)) {
      throw const JsonFieldException('product: OCR product without a page');
    }
    final member = _memberPrice(r, price, currency);
    return Product(
      name: r.nonEmptyString('name'),
      brand: r.optString('brand'),
      quantityText: r.optString('quantity_text'),
      price: Money(price, currency: currency),
      oldPrice: oldPrice == null ? null : Money(oldPrice, currency: currency),
      image: r.optString('image'),
      // A bad page link is not worth losing the product over.
      pageIndex: pageIndex != null && pageIndex >= 0 ? pageIndex : null,
      sourceUrl: r.optString('source_url'),
      source: source,
      memberPrice: member?.$1,
      memberPriceLabel: member?.$2,
    );
  }

  // The member price is optional extra information: anything inconsistent
  // drops it (never the product). Showing a wrong "card price" is worse than
  // showing none.
  static (Money, String)? _memberPrice(
    JsonReader r,
    int shelfPrice,
    String currency,
  ) {
    try {
      final minor = r.optInteger('member_price_minor');
      final label = r.optString('member_price_label')?.trim();
      if (minor == null || label == null || label.isEmpty) return null;
      if (minor < 0 || minor >= shelfPrice) return null;
      return (Money(minor, currency: currency), label);
    } on JsonFieldException {
      return null;
    }
  }

  final String name;
  final String? brand;

  /// Free text such as "700 g", "1,5 L", "4 x 36 g".
  final String? quantityText;

  final Money price;

  /// Struck-through "before" price, when the chain printed one.
  final Money? oldPrice;

  /// Product photo URL (absolute or catalog-relative); resolve before loading.
  final String? image;

  /// 0-based index into the brochure's `pages`, when known.
  final int? pageIndex;

  final String? sourceUrl;

  /// Where [price] comes from; see [isOcr].
  final ProductSource source;

  /// True when the price was read from the brochure page by OCR, not taken
  /// from the chain's written list. Show it with the "broşürden okundu"
  /// label and a link to page [pageIndex] (always set for OCR products).
  bool get isOcr => source == ProductSource.ocr;

  /// Lower price paid only by holders of the chain's card (Migros: "Money
  /// ile"). [price] stays the price everyone pays: show this next to it with
  /// [memberPriceLabel], never instead of it. Always below [price]; set
  /// together with [memberPriceLabel] or not at all.
  final Money? memberPrice;

  /// Who gets [memberPrice], as the chain words it, e.g. "Money ile".
  final String? memberPriceLabel;

  bool get hasMemberPrice => memberPrice != null;

  /// Whole-percent discount when [oldPrice] is higher than [price], else null.
  /// About the shelf price only; [memberPrice] plays no part.
  int? get discountPercent {
    final old = oldPrice;
    if (old == null || old.minor <= price.minor || old.minor == 0) return null;
    return ((old.minor - price.minor) * 100 / old.minor).round();
  }

  @override
  bool operator ==(Object other) =>
      other is Product &&
      other.name == name &&
      other.brand == brand &&
      other.quantityText == quantityText &&
      other.price == price &&
      other.oldPrice == oldPrice &&
      other.image == image &&
      other.pageIndex == pageIndex &&
      other.sourceUrl == sourceUrl &&
      other.source == source &&
      other.memberPrice == memberPrice &&
      other.memberPriceLabel == memberPriceLabel;

  @override
  int get hashCode => Object.hash(
    name,
    brand,
    quantityText,
    price,
    oldPrice,
    image,
    pageIndex,
    sourceUrl,
    source,
    memberPrice,
    memberPriceLabel,
  );

  @override
  String toString() => 'Product($name, $price${isOcr ? ', ocr' : ''})';
}

/// Contents of `products/<brochure_id>.json` (the chain's written list) or
/// `products_ocr/<brochure_id>.json` (read from the pages by OCR).
class ProductFile {
  ProductFile({
    required this.schemaVersion,
    required this.brochureId,
    required this.currency,
    required List<Product> products,
    this.skippedCount = 0,
    this.source = ProductSource.written,
  }) : products = List.unmodifiable(products);

  /// Broken product records are skipped and counted; a bad root throws
  /// [CatalogFormatException].
  ///
  /// [source] is [ProductSource.ocr] for the file behind
  /// `ocr_products_url`: every product is then OCR (see [Product.fromJson]),
  /// and with [pageCount] (the brochure's number of pages) an OCR product
  /// whose page does not exist is skipped too, since its price could not be
  /// shown next to its page.
  factory ProductFile.fromJson(
    Object? json, {
    ProductSource source = ProductSource.written,
    int? pageCount,
  }) {
    final JsonReader root;
    final int schemaVersion;
    final String brochureId;
    final String currency;
    final List<dynamic> rawProducts;
    try {
      root = JsonReader(json, context: 'products');
      schemaVersion = root.integer('schema_version');
      brochureId = root.string('brochure_id');
      currency = root.string('currency');
      rawProducts = root.list('products');
    } on JsonFieldException catch (e) {
      throw CatalogFormatException(e.message, e);
    }
    final ocrFile = source == ProductSource.ocr;
    final products = <Product>[];
    var skipped = 0;
    for (final raw in rawProducts) {
      try {
        final product = Product.fromJson(
          raw,
          currency: currency,
          ocrFile: ocrFile,
        );
        if (product.isOcr &&
            pageCount != null &&
            product.pageIndex! >= pageCount) {
          skipped++;
          continue;
        }
        products.add(product);
      } on JsonFieldException {
        skipped++;
      }
    }
    return ProductFile(
      schemaVersion: schemaVersion,
      brochureId: brochureId,
      currency: currency,
      products: products,
      skippedCount: skipped,
      source: source,
    );
  }

  /// See [ProductFile.fromJson] for [source] and [pageCount].
  factory ProductFile.parse(
    String body, {
    ProductSource source = ProductSource.written,
    int? pageCount,
  }) {
    final Object? decoded;
    try {
      decoded = jsonDecode(body);
    } on FormatException catch (e) {
      throw CatalogFormatException('product file is not valid JSON', e);
    }
    return ProductFile.fromJson(decoded, source: source, pageCount: pageCount);
  }

  final int schemaVersion;
  final String brochureId;

  /// ISO 4217 code shared by every price in the file (`TRY`).
  final String currency;

  /// Products in the chain's own order.
  final List<Product> products;

  final int skippedCount;

  /// Which list this is: the chain's written one or the OCR one. Every
  /// product of an OCR file has [Product.isOcr]; a written file may still
  /// carry single OCR products, so label per product, not per file.
  final ProductSource source;

  /// True for the OCR list (`ocr_products_url`).
  bool get isOcr => source == ProductSource.ocr;

  @override
  bool operator ==(Object other) =>
      other is ProductFile &&
      other.schemaVersion == schemaVersion &&
      other.brochureId == brochureId &&
      other.currency == currency &&
      listEquals(other.products, products) &&
      other.skippedCount == skippedCount &&
      other.source == source;

  @override
  int get hashCode => Object.hash(
    schemaVersion,
    brochureId,
    currency,
    Object.hashAll(products),
    skippedCount,
    source,
  );

  @override
  String toString() =>
      'ProductFile($brochureId, ${products.length} products'
      '${isOcr ? ', ocr' : ''})';
}
