/// Loading images named in the catalog (covers, pages, product photos).
///
/// Every URL goes through `CatalogRepository.resolve` and then through the
/// disk cache, which is what makes a brochure readable without internet
/// after it has been opened once. Tests replace [catalogImageFactoryProvider]
/// and [pagePrefetcherProvider] so no plugin or network is touched.
library;

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_cache_manager/flutter_cache_manager.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/data.dart';
import '../theme.dart';
import '../tokens.dart';

/// Turns a resolved network address into an image provider.
typedef CatalogImageFactory = ImageProvider<Object> Function(Uri uri);

/// Saves one network image to the disk cache (no-op if already there).
typedef PagePrefetcher = Future<void> Function(Uri uri);

/// Disk cache of brochure images; see [AppCachePolicy].
final pageCacheManagerProvider = Provider<BaseCacheManager>((ref) {
  return CacheManager(
    Config(
      AppCachePolicy.key,
      stalePeriod: AppCachePolicy.keepFor,
      maxNrOfCacheObjects: AppCachePolicy.maxObjects,
    ),
  );
});

/// Network images come from the disk cache first.
final catalogImageFactoryProvider = Provider<CatalogImageFactory>((ref) {
  final manager = ref.watch(pageCacheManagerProvider);
  return (uri) =>
      CachedNetworkImageProvider(uri.toString(), cacheManager: manager);
});

/// Downloads an image into the disk cache for later offline reading.
final pagePrefetcherProvider = Provider<PagePrefetcher>((ref) {
  final manager = ref.watch(pageCacheManagerProvider);
  return (uri) async {
    await manager.getSingleFile(uri.toString());
  };
});

/// Image provider for a catalog [url] (absolute or catalog-relative).
///
/// [decodeWidth] / [decodeHeight] cap the decoded size in pixels; the image
/// is never enlarged.
ImageProvider<Object> catalogImageProvider(
  WidgetRef ref,
  String url, {
  int? decodeWidth,
  int? decodeHeight,
}) {
  final uri = ref.watch(catalogRepositoryProvider).resolve(url);
  final ImageProvider<Object> base = uri.isBundledAsset
      ? AssetImage(uri.assetKey)
      : ref.watch(catalogImageFactoryProvider)(uri);
  if (decodeWidth == null && decodeHeight == null) return base;
  return ResizeImage(
    base,
    width: decodeWidth,
    height: decodeHeight,
    policy: ResizeImagePolicy.fit,
  );
}

/// A catalog image for lists (covers, product photos). While it loads, and
/// when it cannot be loaded, [placeholder] is shown instead: a list never
/// shows a broken image or a spinner per row.
class CatalogImage extends ConsumerWidget {
  const CatalogImage({
    super.key,
    required this.url,
    required this.placeholder,
    this.fit = BoxFit.cover,
    this.logicalWidth,
  });

  /// Null shows the placeholder.
  final String? url;
  final Widget placeholder;
  final BoxFit fit;

  /// Displayed width in dp, used to decode no more pixels than needed.
  final double? logicalWidth;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final address = url;
    if (address == null || address.isEmpty) return placeholder;
    final dpr = MediaQuery.devicePixelRatioOf(context);
    final provider = catalogImageProvider(
      ref,
      address,
      decodeWidth: logicalWidth == null ? null : (logicalWidth! * dpr).ceil(),
    );
    return Image(
      image: provider,
      fit: fit,
      excludeFromSemantics: true,
      filterQuality: FilterQuality.medium,
      frameBuilder: (context, child, frame, wasSynchronouslyLoaded) {
        if (wasSynchronouslyLoaded) return child;
        return AnimatedSwitcher(
          duration: context.motion(AppMotion.normal),
          child: frame == null
              ? KeyedSubtree(
                  key: const ValueKey('placeholder'),
                  child: placeholder,
                )
              : KeyedSubtree(key: const ValueKey('image'), child: child),
        );
      },
      errorBuilder: (context, error, stackTrace) => placeholder,
    );
  }
}

/// Paper-coloured stand-in for a brochure cover that has no image (yet).
class CoverPlaceholder extends StatelessWidget {
  const CoverPlaceholder({super.key, this.icon = Icons.menu_book_rounded});

  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return ColoredBox(
      color: c.surfaceSunken,
      child: Center(
        child: Icon(icon, size: AppSize.iconLarge, color: c.lineStrong),
      ),
    );
  }
}
