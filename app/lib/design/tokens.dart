/// Design tokens of Çarşı Pazar: every colour, size, radius and duration the
/// interface uses. Screen code never writes `Color(0x...)` or a bare number;
/// it reads a token from here. Rationale for each choice is in `DESIGN.md`.
library;

import 'package:flutter/material.dart';

/// Colour roles. Read with `context.colors` (see `theme.dart`).
///
/// The palette is "paper and ink": warm cream paper, warm near-black ink and
/// a single deep bazaar green for actions. Market logos and brochure pages
/// are loud; the interface around them stays quiet.
@immutable
class AppColors extends ThemeExtension<AppColors> {
  const AppColors({
    required this.brightness,
    required this.paper,
    required this.surface,
    required this.surfaceSunken,
    required this.ink,
    required this.inkSoft,
    required this.line,
    required this.lineStrong,
    required this.primary,
    required this.onPrimary,
    required this.primarySoft,
    required this.onPrimarySoft,
    required this.star,
    required this.starOutline,
    required this.fresh,
    required this.onFresh,
    required this.notice,
    required this.onNotice,
    required this.noticeLine,
    required this.logoPlate,
    required this.pageSheet,
    required this.shadow,
    required this.onBrandDark,
    required this.onBrandLight,
  });

  final Brightness brightness;

  /// Screen background.
  final Color paper;

  /// Cards and bars that sit on [paper].
  final Color surface;

  /// The "table" a brochure page lies on, image placeholders, skeletons.
  final Color surfaceSunken;

  /// Main text and icons.
  final Color ink;

  /// Secondary text. Still at least 7:1 on [paper].
  final Color inkSoft;

  /// Hairline dividers and card edges.
  final Color line;

  /// Outlines of controls (at least 3:1 on [paper]).
  final Color lineStrong;

  /// The one action colour: main buttons, selected tab.
  final Color primary;
  final Color onPrimary;

  /// Quiet tint of [primary]: tonal buttons, favourites header.
  final Color primarySoft;
  final Color onPrimarySoft;

  /// Favourite star fill, and its outline (the outline keeps the shape
  /// visible for people who cannot tell the fill colour apart).
  final Color star;
  final Color starOutline;

  /// "Yeni" badge and discount tag.
  final Color fresh;
  final Color onFresh;

  /// Calm notice strip (offline, outdated data, update needed).
  final Color notice;
  final Color onNotice;
  final Color noticeLine;

  /// Plate behind a market logo. Stays (near) white in both themes because
  /// logos are drawn for a white background.
  final Color logoPlate;

  /// Paper colour behind a brochure page while it loads.
  final Color pageSheet;

  final Color shadow;

  /// Text colours used on top of a market's brand colour (name cards). The
  /// one with the higher contrast is picked at runtime.
  final Color onBrandDark;
  final Color onBrandLight;

  static const AppColors light = AppColors(
    brightness: Brightness.light,
    paper: Color(0xFFF6F1E7),
    surface: Color(0xFFFFFDF9),
    surfaceSunken: Color(0xFFE9E1D1),
    ink: Color(0xFF1D1A16),
    inkSoft: Color(0xFF564E44),
    line: Color(0xFFDDD4C2),
    lineStrong: Color(0xFF8A7F6D),
    primary: Color(0xFF1F5A45),
    onPrimary: Color(0xFFFFFFFF),
    primarySoft: Color(0xFFDCE9DF),
    onPrimarySoft: Color(0xFF143D2F),
    star: Color(0xFFF2B01E),
    starOutline: Color(0xFF6B4A00),
    fresh: Color(0xFFB5281C),
    onFresh: Color(0xFFFFFFFF),
    notice: Color(0xFFFBEBC2),
    onNotice: Color(0xFF3D2E00),
    noticeLine: Color(0xFFDDBF6A),
    logoPlate: Color(0xFFFFFFFF),
    pageSheet: Color(0xFFFFFDF9),
    shadow: Color(0x24322A1C),
    onBrandDark: Color(0xFF000000),
    onBrandLight: Color(0xFFFFFFFF),
  );

  static const AppColors dark = AppColors(
    brightness: Brightness.dark,
    paper: Color(0xFF161411),
    surface: Color(0xFF24211C),
    surfaceSunken: Color(0xFF0D0C0A),
    ink: Color(0xFFF4EEE3),
    inkSoft: Color(0xFFC6BCAC),
    line: Color(0xFF3B362E),
    lineStrong: Color(0xFF8E8473),
    primary: Color(0xFF8AD4B0),
    onPrimary: Color(0xFF0B2A1F),
    primarySoft: Color(0xFF213F33),
    onPrimarySoft: Color(0xFFCFEBDD),
    star: Color(0xFFFFC83D),
    starOutline: Color(0xFFFFC83D),
    fresh: Color(0xFFFF9D8C),
    onFresh: Color(0xFF3B0A05),
    notice: Color(0xFF3A2F12),
    onNotice: Color(0xFFFBE7B5),
    noticeLine: Color(0xFF6B5720),
    logoPlate: Color(0xFFFAF8F4),
    pageSheet: Color(0xFF2E2A24),
    shadow: Color(0x66000000),
    onBrandDark: Color(0xFF000000),
    onBrandLight: Color(0xFFFFFFFF),
  );

  bool get isDark => brightness == Brightness.dark;

  /// The readable text colour on top of [background] (a brand colour).
  Color onBrand(Color background) =>
      contrastRatio(onBrandLight, background) >=
          contrastRatio(onBrandDark, background)
      ? onBrandLight
      : onBrandDark;

  @override
  AppColors copyWith() => this;

  @override
  AppColors lerp(ThemeExtension<AppColors>? other, double t) {
    if (other is! AppColors) return this;
    return t < 0.5 ? this : other;
  }
}

/// WCAG 2 contrast ratio between two opaque colours (1.0 – 21.0).
double contrastRatio(Color a, Color b) {
  final la = a.computeLuminance();
  final lb = b.computeLuminance();
  final hi = la > lb ? la : lb;
  final lo = la > lb ? lb : la;
  return (hi + 0.05) / (lo + 0.05);
}

/// Spacing scale (dp). Use these, not literals.
abstract final class AppSpace {
  static const double xxs = 4;
  static const double xs = 8;
  static const double sm = 12;
  static const double md = 16;
  static const double lg = 20;
  static const double xl = 24;
  static const double xxl = 32;
  static const double xxxl = 48;

  /// Left/right margin of every screen.
  static const double screen = 16;

  /// Gap between two cards of the home grid.
  static const double grid = 12;
}

/// Corner radii (dp).
abstract final class AppRadius {
  static const double sm = 10;
  static const double md = 14;
  static const double lg = 20;
  static const double pill = 999;

  static const BorderRadius smAll = BorderRadius.all(Radius.circular(sm));
  static const BorderRadius mdAll = BorderRadius.all(Radius.circular(md));
  static const BorderRadius lgAll = BorderRadius.all(Radius.circular(lg));
  static const BorderRadius pillAll = BorderRadius.all(Radius.circular(pill));
}

/// Sizes of controls and fixed parts (dp).
abstract final class AppSize {
  /// Smallest touch target anywhere in the app.
  static const double touch = 56;

  /// Main buttons and the viewer's arrow buttons.
  static const double touchLarge = 64;

  static const double icon = 28;
  static const double iconLarge = 34;
  static const double iconSmall = 22;

  /// Height of the top bar that carries "Geri".
  static const double topBar = 72;

  static const double hairline = 1;
  static const double outline = 2;

  /// Thickness of the keyboard / switch-access focus ring.
  static const double focusRing = 3;

  /// Home card: height of the logo plate.
  static const double chainPlate = 104;

  /// Market screen: width of a brochure cover.
  static const double cover = 116;
  static const double coverHero = 148;

  /// Cover width when the system font is very large (text needs the room).
  static const double coverCompact = 84;

  /// Height of the market plate in the market screen's top bar.
  static const double topBarMark = 52;
  static const double topBarMarkWidth = 132;

  /// Fallback page shape (A4-like) when the catalog gives no dimensions.
  static const double pageAspectFallback = 0.707;

  /// Product photo in a product card.
  static const double productImage = 88;

  /// Splash logo.
  static const double splashLogo = 168;

  /// Logo in the home header.
  static const double headerLogo = 52;

  /// Illustration size in empty / error views.
  static const double stateArt = 112;

  /// Content never grows wider than this on tablets / landscape.
  static const double maxContentWidth = 640;

  /// Width below which the home grid falls back to a single column when the
  /// system font is very large.
  static const double minCardWidth = 150;
}

/// Zoom behaviour of the brochure viewer.
abstract final class AppZoom {
  /// Scale reached by one double tap from the fitted page.
  static const double doubleTap = 2.5;

  /// Multiplier of one press on + / −.
  static const double step = 1.6;

  /// Every page can be magnified at least this much, however low its
  /// resolution: a soft big letter is still easier to read than a sharp tiny
  /// one.
  static const double minMax = 4;

  /// Upper limit for very high resolution pages.
  static const double maxMax = 8;

  /// Extra magnification allowed beyond "one image pixel per screen pixel".
  static const double beyondNative = 2;

  /// Below this the page counts as "not zoomed" (swiping turns pages).
  static const double zoomedThreshold = 1.02;

  /// Pages decoded larger than this (px, long side) are downsampled to keep
  /// memory in check.
  static const int maxDecodeSide = 3200;

  /// Brochures up to this many pages are saved completely for offline
  /// reading as soon as they are opened; longer ones are saved as they are
  /// read (plus [prefetchAhead] pages ahead).
  static const int prefetchWholeLimit = 16;
  static const int prefetchAhead = 3;
}

/// Durations and curves. Motion is short and purposeful; all of it is
/// skipped when the system asks for reduced motion.
abstract final class AppMotion {
  static const Duration quick = Duration(milliseconds: 160);
  static const Duration normal = Duration(milliseconds: 240);
  static const Duration zoom = Duration(milliseconds: 260);
  static const Duration page = Duration(milliseconds: 280);

  /// Whole splash sequence.
  static const Duration splash = Duration(milliseconds: 1900);

  /// Longest wait for the first frame to reach the screen before the splash
  /// animation starts anyway.
  static const Duration splashStartLimit = Duration(milliseconds: 1500);

  /// Splash when motion is reduced: a still logo.
  static const Duration splashStill = Duration(milliseconds: 900);

  /// Cross-fade from splash to the home screen.
  static const Duration splashFade = Duration(milliseconds: 320);

  /// How long a snack message stays (long enough to read slowly).
  static const Duration snack = Duration(seconds: 5);

  static const Curve curve = Curves.easeOutCubic;
  static const Curve curveInOut = Curves.easeInOutCubic;
}

/// Elevation recipes.
abstract final class AppShadows {
  static List<BoxShadow> card(AppColors c) => c.isDark
      ? const []
      : [
          BoxShadow(
            color: c.shadow,
            blurRadius: 14,
            offset: const Offset(0, 4),
            spreadRadius: -4,
          ),
        ];

  static List<BoxShadow> page(AppColors c) => [
    BoxShadow(
      color: c.shadow,
      blurRadius: 18,
      offset: const Offset(0, 6),
      spreadRadius: -2,
    ),
  ];
}

/// Image cache policy for brochure pages (offline reading).
abstract final class AppCachePolicy {
  static const String key = 'carsiPazarPages';

  /// A page that was opened once stays readable offline this long.
  static const Duration keepFor = Duration(days: 45);

  static const int maxObjects = 1200;
}
