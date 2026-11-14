import 'dart:convert';

import 'package:flutter/foundation.dart' show listEquals;

import '../errors.dart';
import 'json_reader.dart';
import 'money.dart';

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
    Money? memberPrice,
    String? memberPriceLabel,
  }) : memberPrice = memberPriceLabel == null ? null : memberPrice,
       memberPriceLabel = memberPrice == null ? null : memberPriceLabel;

  /// Throws [JsonFieldException] for a malformed record; the product file
  /// parser skips it.
  factory Product.fromJson(Object? json, {String currency = 'TRY'}) {
    final r = JsonReader(json, context: 'product');
    final price = r.integer('price_minor');
    final oldPrice = r.optInteger('old_price_minor');
    final pageIndex = r.optInteger('page_index');
    if (price < 0 || (oldPrice != null && oldPrice < 0)) {
      throw const JsonFieldException('product: negative price');
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
    memberPrice,
    memberPriceLabel,
  );

  @override
  String toString() => 'Product($name, $price)';
}

/// Contents of `products/<brochure_id>.json`.
class ProductFile {
  ProductFile({
    required this.schemaVersion,
    required this.brochureId,
    required this.currency,
    required List<Product> products,
    this.skippedCount = 0,
  }) : products = List.unmodifiable(products);

  /// Broken product records are skipped and counted; a bad root throws
  /// [CatalogFormatException].
  factory ProductFile.fromJson(Object? json) {
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
    final products = <Product>[];
    var skipped = 0;
    for (final raw in rawProducts) {
      try {
        products.add(Product.fromJson(raw, currency: currency));
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
    );
  }

  factory ProductFile.parse(String body) {
    final Object? decoded;
    try {
      decoded = jsonDecode(body);
    } on FormatException catch (e) {
      throw CatalogFormatException('product file is not valid JSON', e);
    }
    return ProductFile.fromJson(decoded);
  }

  final int schemaVersion;
  final String brochureId;

  /// ISO 4217 code shared by every price in the file (`TRY`).
  final String currency;

  /// Products in the chain's own order.
  final List<Product> products;

  final int skippedCount;

  @override
  bool operator ==(Object other) =>
      other is ProductFile &&
      other.schemaVersion == schemaVersion &&
      other.brochureId == brochureId &&
      other.currency == currency &&
      listEquals(other.products, products) &&
      other.skippedCount == skippedCount;

  @override
  int get hashCode => Object.hash(
    schemaVersion,
    brochureId,
    currency,
    Object.hashAll(products),
    skippedCount,
  );

  @override
  String toString() => 'ProductFile($brochureId, ${products.length} products)';
}
