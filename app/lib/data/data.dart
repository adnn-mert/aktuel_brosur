/// Public face of the data layer. Screens import only this file:
///
/// ```dart
/// import 'package:aktuel_brosur/data/data.dart';
/// ```
library;

export 'brochure_grouping.dart';
export 'cache_store.dart' show CacheEntry, CacheStore, MemoryCacheStore;
export 'catalog_repository.dart';
export 'errors.dart';
export 'favorites_store.dart';
export 'models/brochure.dart';
export 'models/catalog.dart';
export 'models/chain.dart';
export 'models/media_image.dart';
export 'models/money.dart';
export 'models/product.dart';
export 'providers.dart';
