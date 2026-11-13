/// Typed failures the data layer can surface to the UI.
library;

/// The root of a `catalog.json` or product file is unusable (not JSON, not an
/// object, or a required root field is missing or mistyped).
///
/// A single broken chain/brochure/product record never causes this: such
/// records are skipped and counted instead.
class CatalogFormatException implements Exception {
  const CatalogFormatException(this.message, [this.cause]);

  final String message;
  final Object? cause;

  @override
  String toString() => 'CatalogFormatException: $message';
}

/// Base class for "there is nothing to show": the network failed and no
/// usable cached copy exists.
sealed class DataUnavailableException implements Exception {
  const DataUnavailableException(this.message, [this.cause]);

  final String message;

  /// The underlying network/parse error, for logging only.
  final Object? cause;

  @override
  String toString() => '$runtimeType: $message';
}

/// The catalog could not be fetched and there is no cached copy (typically
/// the very first launch while offline).
class CatalogUnavailableException extends DataUnavailableException {
  const CatalogUnavailableException(super.message, [super.cause]);
}

/// A brochure's product list could not be fetched and was never cached, or
/// the brochure has no product list at all.
class ProductsUnavailableException extends DataUnavailableException {
  const ProductsUnavailableException(super.message, [super.cause]);
}
