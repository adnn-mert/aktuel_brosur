// Renders the D4 notification screens to PNG for DESIGN.md. Not part of the
// normal test run (and nothing here ships in the app):
//
//   flutter test test/tools/notification_screenshots_test.dart --dart-define=SCREENSHOTS_DIR=<folder>
//
// Why from a widget test: without the Firebase configuration the real app
// reports notifications as "unavailable" and shows nothing, so the states
// are produced with the same fake provider the widget tests use. Real fonts,
// real logos and real Material icons are loaded, at Medium_Phone size and
// pixel ratio. There is no system status bar in these pictures.
@TestOn('vm')
library;

import 'dart:io';
import 'dart:ui' as ui;

import 'package:aktuel_brosur/data/data.dart';
import 'package:aktuel_brosur/features/home/home_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import '../ui/support.dart';

const String _dir = String.fromEnvironment('SCREENSHOTS_DIR');

/// Medium_Phone: 1080 px wide at 411 dp.
const double _pixelRatio = 2.625;

Future<void> _loadIcons() async {
  final root = Platform.environment['FLUTTER_ROOT'];
  if (root == null) return;
  final file = File(
    '$root/bin/cache/artifacts/material_fonts/MaterialIcons-Regular.otf',
  );
  if (!file.existsSync()) return;
  final bytes = file.readAsBytesSync();
  await (FontLoader(
    'MaterialIcons',
  )..addFont(Future.value(ByteData.view(bytes.buffer)))).load();
}

Future<void> _precacheImages(WidgetTester tester) async {
  await tester.runAsync(() async {
    for (final element in find.byType(Image).evaluate()) {
      await precacheImage((element.widget as Image).image, element);
    }
  });
  await tester.pump();
}

Future<void> _shot(WidgetTester tester, String name) async {
  await _precacheImages(tester);
  await tester.pumpAndSettle();
  await tester.runAsync(() async {
    final view = tester.binding.renderViews.first;
    final layer = view.debugLayer! as OffsetLayer;
    final size = tester.view.physicalSize / tester.view.devicePixelRatio;
    final image = await layer.toImage(
      Offset.zero & size,
      pixelRatio: _pixelRatio,
    );
    final data = await image.toByteData(format: ui.ImageByteFormat.png);
    image.dispose();
    File('$_dir/$name.png')
      ..createSync(recursive: true)
      ..writeAsBytesSync(data!.buffer.asUint8List());
  });
}

Future<void> _home(
  WidgetTester tester, {
  required NotificationsStatus status,
  Set<String> favorites = const {'sok', 'bim'},
  Brightness brightness = Brightness.light,
  double textScale = 1,
  Size size = phoneSize,
}) async {
  await pumpUi(
    tester,
    const HomeScreen(),
    overrides: uiOverrides(favorites: favorites, notifications: status),
    brightness: brightness,
    textScale: textScale,
    size: size,
  );
  await tester.pumpAndSettle();
}

/// Scrolls the home list so the panel with [key] starts near the top.
Future<void> _scrollTo(WidgetTester tester, Key key) async {
  await Scrollable.ensureVisible(
    tester.element(find.byKey(key)),
    alignment: 0.05,
  );
  await tester.pumpAndSettle();
}

Future<void> _firstStar(
  WidgetTester tester, {
  Brightness brightness = Brightness.light,
  double textScale = 1,
  Size size = phoneSize,
}) async {
  await _home(
    tester,
    status: NotificationsStatus.off,
    favorites: const {},
    brightness: brightness,
    textScale: textScale,
    size: size,
  );
  final star = find.bySemanticsLabel(l10nOf(tester).favoriteAdd('Şok'));
  await tester.ensureVisible(star);
  await tester.pumpAndSettle();
  await tester.tap(star);
  await tester.pumpAndSettle();
}

void main() {
  setUpAll(() async {
    // test/tools has no flutter_test_config.dart of its own.
    await loadAppFonts();
    await _loadIcons();
  });

  final skip = _dir.isEmpty;

  testWidgets('61 off', skip: skip, (tester) async {
    await _home(tester, status: NotificationsStatus.off);
    await _shot(tester, '61-bildirim-kapali');
  });

  testWidgets('62 offer after the first star', skip: skip, (tester) async {
    await _firstStar(tester);
    await _shot(tester, '62-bildirim-ilk-yildiz-teklif');
  });

  testWidgets('63 on', skip: skip, (tester) async {
    await _home(tester, status: NotificationsStatus.on);
    await _shot(tester, '63-bildirim-acik');
  });

  testWidgets('64 blocked', skip: skip, (tester) async {
    await _home(tester, status: NotificationsStatus.blockedBySystem);
    await _shot(tester, '64-bildirim-telefonda-kapali');
  });

  testWidgets('65 dark offer', skip: skip, (tester) async {
    await _firstStar(tester, brightness: Brightness.dark);
    await _shot(tester, '65-koyu-bildirim-teklif');
  });

  testWidgets('66 dark on', skip: skip, (tester) async {
    await _home(
      tester,
      status: NotificationsStatus.on,
      brightness: Brightness.dark,
    );
    await _shot(tester, '66-koyu-bildirim-acik');
  });

  testWidgets('67 large text offer', skip: skip, (tester) async {
    await _firstStar(tester, textScale: 2);
    await _shot(tester, '67-buyuk-yazi-bildirim-teklif');
  });

  testWidgets('68 large text on', skip: skip, (tester) async {
    await _home(tester, status: NotificationsStatus.on, textScale: 2);
    await _scrollTo(tester, const ValueKey('notify-on'));
    await _shot(tester, '68-buyuk-yazi-bildirim-acik');
  });

  testWidgets('69 small phone, large text, blocked', skip: skip, (
    tester,
  ) async {
    await _home(
      tester,
      status: NotificationsStatus.blockedBySystem,
      textScale: 2,
      size: const Size(320, 640),
    );
    // The written steps open (as when the settings page cannot open); the
    // picture starts at the settings button.
    await _scrollTo(tester, const ValueKey('notify-how-to'));
    await tester.tap(find.byKey(const ValueKey('notify-how-to')));
    await tester.pumpAndSettle();
    await _scrollTo(tester, const ValueKey('notify-open-settings'));
    await _shot(tester, '69-kucuk-ekran-buyuk-yazi-telefonda-kapali');
  });
}
