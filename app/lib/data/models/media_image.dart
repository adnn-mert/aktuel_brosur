import 'json_reader.dart';

/// An image reference from the catalog: a brochure page, a cover or a logo.
///
/// [url] is exactly as published (absolute `https://` or relative to
/// `catalog.json`); turn it into something loadable with
/// `CatalogRepository.resolve`.
class MediaImage {
  const MediaImage({required this.url, this.width, this.height});

  factory MediaImage.fromJson(Object? json, {String context = 'image'}) {
    final r = JsonReader(json, context: context);
    final width = r.optInteger('w');
    final height = r.optInteger('h');
    if ((width != null && width < 1) || (height != null && height < 1)) {
      throw JsonFieldException('$context: w/h must be positive');
    }
    return MediaImage(
      url: r.nonEmptyString('url'),
      width: width,
      height: height,
    );
  }

  final String url;

  /// Pixel width, if the scraper knew it.
  final int? width;

  /// Pixel height, if the scraper knew it.
  final int? height;

  /// width / height, or null when either is unknown. Use it to reserve space
  /// before the image arrives so pages do not jump while loading.
  double? get aspectRatio =>
      (width != null && height != null) ? width! / height! : null;

  @override
  bool operator ==(Object other) =>
      other is MediaImage &&
      other.url == url &&
      other.width == width &&
      other.height == height;

  @override
  int get hashCode => Object.hash(url, width, height);

  @override
  String toString() => 'MediaImage($url, ${width}x$height)';
}
