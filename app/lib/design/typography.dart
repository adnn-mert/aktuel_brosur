/// Type scale. Two embedded families (both SIL OFL, shipped in
/// `assets/fonts/`, never downloaded at runtime):
///
/// * **Lexend** for everything that is read or pressed. Wide, open letters
///   with generous spacing, designed around reading-ease research; complete
///   Turkish set and the ₺ sign.
/// * **Fraunces** (semi-bold) for the few big headings, to give the app the
///   voice of a printed brochure.
///
/// No text style is smaller than 18 sp.
library;

import 'package:flutter/material.dart';

abstract final class AppFonts {
  static const String text = 'Lexend';
  static const String display = 'Fraunces';
}

/// Named text styles. Colours are applied by the theme / the widget.
abstract final class AppType {
  /// App name on the splash and home header.
  static const TextStyle wordmark = TextStyle(
    fontFamily: AppFonts.display,
    fontWeight: FontWeight.w600,
    fontSize: 34,
    height: 1.15,
    letterSpacing: -0.3,
  );

  /// Screen titles (market name, "Hangi markete bakalım?").
  static const TextStyle headline = TextStyle(
    fontFamily: AppFonts.display,
    fontWeight: FontWeight.w600,
    fontSize: 28,
    height: 1.2,
    letterSpacing: -0.2,
  );

  /// Section headings ("Bu hafta").
  static const TextStyle section = TextStyle(
    fontFamily: AppFonts.display,
    fontWeight: FontWeight.w600,
    fontSize: 24,
    height: 1.25,
  );

  /// Card titles, dates, top-bar title.
  static const TextStyle title = TextStyle(
    fontFamily: AppFonts.text,
    fontWeight: FontWeight.w600,
    fontSize: 21,
    height: 1.3,
  );

  /// Running text.
  static const TextStyle body = TextStyle(
    fontFamily: AppFonts.text,
    fontWeight: FontWeight.w400,
    fontSize: 18,
    height: 1.45,
  );

  /// Emphasised running text, captions on cards.
  static const TextStyle bodyStrong = TextStyle(
    fontFamily: AppFonts.text,
    fontWeight: FontWeight.w600,
    fontSize: 18,
    height: 1.35,
  );

  /// Button labels.
  static const TextStyle label = TextStyle(
    fontFamily: AppFonts.text,
    fontWeight: FontWeight.w600,
    fontSize: 20,
    height: 1.2,
  );

  /// Small pills ("Yeni", "%20 indirim"). Still 18 sp.
  static const TextStyle badge = TextStyle(
    fontFamily: AppFonts.text,
    fontWeight: FontWeight.w700,
    fontSize: 18,
    height: 1.15,
  );

  /// Market name on a name card (no logo file).
  static const TextStyle chainName = TextStyle(
    fontFamily: AppFonts.text,
    fontWeight: FontWeight.w700,
    fontSize: 38,
    height: 1.1,
    letterSpacing: -0.4,
  );

  /// Price on a product card.
  static const TextStyle price = TextStyle(
    fontFamily: AppFonts.text,
    fontWeight: FontWeight.w700,
    fontSize: 28,
    height: 1.15,
    fontFeatures: [FontFeature.tabularFigures()],
  );

  /// Crossed-out earlier price.
  static const TextStyle priceOld = TextStyle(
    fontFamily: AppFonts.text,
    fontWeight: FontWeight.w500,
    fontSize: 18,
    height: 1.2,
    decoration: TextDecoration.lineThrough,
    fontFeatures: [FontFeature.tabularFigures()],
  );

  /// "3 / 8" in the viewer.
  static const TextStyle pageIndicator = TextStyle(
    fontFamily: AppFonts.text,
    fontWeight: FontWeight.w700,
    fontSize: 24,
    height: 1.1,
    fontFeatures: [FontFeature.tabularFigures()],
  );
}

/// The app honours the system font size up to this factor (Android's own
/// maximum is 2.0). Layouts are built to survive it.
const double maxTextScale = 2.0;
