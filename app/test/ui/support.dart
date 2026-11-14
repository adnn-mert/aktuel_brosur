// Shared helpers of the interface tests: a fake repository over the bundled
// sample data, image providers that need no network, and a `pumpUi` that
// wraps a widget in the real theme and localisation.

import 'dart:io';
import 'dart:ui' as ui;

import 'package:aktuel_brosur/data/data.dart';
import 'package:aktuel_brosur/design/theme.dart';
import 'package:aktuel_brosur/design/typography.dart';
import 'package:aktuel_brosur/design/widgets/catalog_image.dart';
import 'package:aktuel_brosur/l10n/app_localizations.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/misc.dart' show Override;
import 'package:flutter_test/flutter_test.dart';

import '../helpers.dart';

/// Medium_Phone in dp.
const Size phoneSize = Size(411, 914);

/// Loads the app's real fonts so text is measured as on a device (the test
/// default font is far wider and would report overflows that do not exist).
Future<void> loadAppFonts() async {
  Future<ByteData> read(String file) async =>
      ByteData.view(File('assets/fonts/$file').readAsBytesSync().buffer);
  await (FontLoader(AppFonts.text)
        ..addFont(read('Lexend-Regular.ttf'))
        ..addFont(read('Lexend-Medium.ttf'))
        ..addFont(read('Lexend-SemiBold.ttf'))
        ..addFont(read('Lexend-Bold.ttf')))
      .load();
  await (FontLoader(
    AppFonts.display,
  )..addFont(read('Fraunces-SemiBold.ttf'))).load();
}

/// Serves the sample catalog instantly; can be told to fail or be stale.
class FakeRepository implements CatalogRepository {
  FakeRepository({
    Catalog? catalog,
    this.error,
    this.isStale = false,
    this.productsError,
  }) : catalog = catalog ?? sampleCatalog();

  Catalog catalog;
  Object? error;
  bool isStale;
  Object? productsError;

  @override
  Future<CatalogResult> loadCatalog({bool forceRefresh = false}) async {
    final failure = error;
    if (failure != null) throw failure;
    return CatalogResult(
      catalog: catalog,
      source: isStale ? CatalogSource.cache : CatalogSource.network,
      fetchedAt: DateTime.utc(2026, 11, 12, 15),
      isStale: isStale,
    );
  }

  @override
  Future<ProductFile> loadProducts(Brochure brochure) async {
    final failure = productsError;
    if (failure != null) throw failure;
    return ProductFile.parse(sampleText(brochure.productsUrl!));
  }

  @override
  Uri resolve(String url) {
    final parsed = Uri.parse(url);
    return parsed.hasScheme
        ? parsed
        : Uri(scheme: 'asset', path: 'assets/sample/').resolveUri(parsed);
  }
}

/// An image that is ready immediately (or fails immediately).
class TestImageProvider extends ImageProvider<TestImageProvider> {
  TestImageProvider(this.image, {this.fail = false});

  final ui.Image? image;
  final bool fail;

  @override
  Future<TestImageProvider> obtainKey(ImageConfiguration configuration) =>
      SynchronousFuture(this);

  @override
  ImageStreamCompleter loadImage(
    TestImageProvider key,
    ImageDecoderCallback decode,
  ) {
    if (fail || image == null) {
      return OneFrameImageStreamCompleter(
        Future<ImageInfo>.error(StateError('test image failure')),
      );
    }
    return OneFrameImageStreamCompleter(
      SynchronousFuture(ImageInfo(image: image!.clone())),
    );
  }
}

/// A 200 × 300 picture for page and cover images.
Future<ui.Image> makeTestImage(WidgetTester tester) async =>
    (await tester.runAsync(() => createTestImage(width: 200, height: 300)))!;

/// Provider overrides every interface test needs.
List<Override> uiOverrides({
  FakeRepository? repository,
  ui.Image? image,
  bool imagesFail = false,
  Set<String> favorites = const {},
}) => [
  catalogRepositoryProvider.overrideWithValue(repository ?? FakeRepository()),
  favoritesStoreProvider.overrideWithValue(MemoryFavoritesStore(favorites)),
  clockProvider.overrideWithValue(Clock.fixed(sampleToday)),
  catalogImageFactoryProvider.overrideWithValue(
    (uri) => TestImageProvider(image, fail: imagesFail),
  ),
  pagePrefetcherProvider.overrideWithValue((uri) async {}),
];

/// Pumps [child] inside the real theme, localisation and a phone-sized
/// surface.
Future<void> pumpUi(
  WidgetTester tester,
  Widget child, {
  List<Override> overrides = const [],
  Brightness brightness = Brightness.light,
  double textScale = 1,
  bool reduceMotion = false,
  Size size = phoneSize,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    ProviderScope(
      overrides: overrides,
      child: MaterialApp(
        debugShowCheckedModeBanner: false,
        locale: const Locale('tr'),
        supportedLocales: AppLocalizations.supportedLocales,
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        theme: buildAppTheme(brightness),
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context).copyWith(
            textScaler: TextScaler.linear(textScale),
            disableAnimations: reduceMotion,
          ),
          child: child!,
        ),
        home: child,
      ),
    ),
  );
  // Let the catalog future and the favourites future complete.
  await tester.pump();
  await tester.pump();
}

AppLocalizations l10nOf(WidgetTester tester) =>
    AppLocalizations.of(tester.element(find.byType(Scaffold).first));
