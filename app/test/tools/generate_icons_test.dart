// Generates the launcher icons from the logo drawing (LogoPainter), so the
// icon can never drift from the logo. Not part of the normal test run:
//
//   flutter test test/tools/generate_icons_test.dart --dart-define=GENERATE_ICONS=true
//
// Optional: --dart-define=LOGO_PREVIEW_DIR=<folder> also writes large
// previews of the mark (paper, dark, icon, mid-flip frames) for review.
@TestOn('vm')
library;

import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:aktuel_brosur/design/widgets/logo_mark.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const bool _generate = bool.fromEnvironment('GENERATE_ICONS');
const String _previewDir = String.fromEnvironment('LOGO_PREVIEW_DIR');

/// Share of the legacy icon the mark fills.
const double _legacyMarkScale = 0.86;

/// Share of the 108 dp adaptive canvas the mark fills (safe zone is 66 dp).
const double _adaptiveMarkScale = 0.64;

/// Corner radius of the legacy icon as a share of its side.
const double _legacyRadius = 0.22;

Future<Uint8List> _render(
  int size, {
  required LogoPalette palette,
  required double markScale,
  Color? background,
  double radius = 0,
  List<PageFlip> flips = const [],
}) async {
  final recorder = ui.PictureRecorder();
  final canvas = Canvas(recorder);
  final side = size.toDouble();
  if (background != null) {
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(0, 0, side, side),
        Radius.circular(side * radius),
      ),
      Paint()..color = background,
    );
  }
  final mark = side * markScale;
  canvas.translate((side - mark) / 2, (side - mark) / 2);
  LogoPainter(palette: palette, flips: flips).paint(canvas, Size.square(mark));
  final image = await recorder.endRecording().toImage(size, size);
  final data = await image.toByteData(format: ui.ImageByteFormat.png);
  image.dispose();
  return data!.buffer.asUint8List();
}

void _write(String path, Uint8List bytes) {
  File(path)
    ..createSync(recursive: true)
    ..writeAsBytesSync(bytes);
}

void main() {
  testWidgets('generate launcher icons', (tester) async {
    await tester.runAsync(() async {
      const res = 'android/app/src/main/res';
      const densities = {
        'mdpi': 1.0,
        'hdpi': 1.5,
        'xhdpi': 2.0,
        'xxhdpi': 3.0,
        'xxxhdpi': 4.0,
      };
      for (final MapEntry(key: name, value: factor) in densities.entries) {
        _write(
          '$res/mipmap-$name/ic_launcher.png',
          await _render(
            (48 * factor).round(),
            palette: LogoPalette.onGreen,
            markScale: _legacyMarkScale,
            background: LogoPalette.iconBackground,
            radius: _legacyRadius,
          ),
        );
        _write(
          '$res/mipmap-$name/ic_launcher_foreground.png',
          await _render(
            (108 * factor).round(),
            palette: LogoPalette.onGreen,
            markScale: _adaptiveMarkScale,
          ),
        );
      }

      const ios = 'ios/Runner/Assets.xcassets/AppIcon.appiconset';
      const iosSizes = {
        'Icon-App-20x20@1x.png': 20,
        'Icon-App-20x20@2x.png': 40,
        'Icon-App-20x20@3x.png': 60,
        'Icon-App-29x29@1x.png': 29,
        'Icon-App-29x29@2x.png': 58,
        'Icon-App-29x29@3x.png': 87,
        'Icon-App-40x40@1x.png': 40,
        'Icon-App-40x40@2x.png': 80,
        'Icon-App-40x40@3x.png': 120,
        'Icon-App-60x60@2x.png': 120,
        'Icon-App-60x60@3x.png': 180,
        'Icon-App-76x76@1x.png': 76,
        'Icon-App-76x76@2x.png': 152,
        'Icon-App-83.5x83.5@2x.png': 167,
        'Icon-App-1024x1024@1x.png': 1024,
      };
      for (final MapEntry(key: file, value: size) in iosSizes.entries) {
        // iOS icons are opaque squares; the system rounds the corners.
        _write(
          '$ios/$file',
          await _render(
            size,
            palette: LogoPalette.onGreen,
            markScale: _legacyMarkScale,
            background: LogoPalette.iconBackground,
          ),
        );
      }
    });
  }, skip: !_generate);

  testWidgets('write logo previews', (tester) async {
    await tester.runAsync(() async {
      const paper = Color(0xFFF6F1E7);
      const night = Color(0xFF161411);
      _write(
        '$_previewDir/logo_paper.png',
        await _render(
          512,
          palette: LogoPalette.onPaper,
          markScale: 0.9,
          background: paper,
        ),
      );
      _write(
        '$_previewDir/logo_dark.png',
        await _render(
          512,
          palette: LogoPalette.onDark,
          markScale: 0.9,
          background: night,
        ),
      );
      _write(
        '$_previewDir/logo_icon.png',
        await _render(
          512,
          palette: LogoPalette.onGreen,
          markScale: _legacyMarkScale,
          background: LogoPalette.iconBackground,
          radius: _legacyRadius,
        ),
      );
      _write(
        '$_previewDir/logo_small.png',
        await _render(
          96,
          palette: LogoPalette.onPaper,
          markScale: 1,
          background: paper,
        ),
      );
      final tints = LogoPalette.onPaper.flipTints;
      for (final (i, progress) in [0.2, 0.4, 0.5, 0.6, 0.8].indexed) {
        _write(
          '$_previewDir/logo_flip_$i.png',
          await _render(
            512,
            palette: LogoPalette.onPaper,
            markScale: 0.9,
            background: paper,
            flips: [
              PageFlip(progress: progress, tint: tints[i]),
              if (progress > 0.3)
                PageFlip(progress: progress - 0.25, tint: tints[i + 1]),
            ],
          ),
        );
      }
    });
  }, skip: _previewDir.isEmpty);
}
