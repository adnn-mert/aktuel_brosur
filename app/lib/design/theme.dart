/// Material theme built from the tokens. Screens style themselves through
/// `context.colors` and `AppType`; this file only makes the stock Material
/// widgets (snack bars, ink ripples, progress rings, scrollbars) agree with
/// the same palette.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'tokens.dart';
import 'typography.dart';

extension AppThemeContext on BuildContext {
  /// The colour roles of the active theme.
  AppColors get colors => Theme.of(this).extension<AppColors>()!;

  /// True when the system asks for reduced motion. Every animation in the
  /// app checks this.
  bool get reduceMotion => MediaQuery.disableAnimationsOf(this);

  /// [duration], or zero when motion is reduced.
  Duration motion(Duration duration) => reduceMotion ? Duration.zero : duration;
}

ThemeData buildAppTheme(Brightness brightness) {
  final c = brightness == Brightness.dark ? AppColors.dark : AppColors.light;

  final scheme = ColorScheme(
    brightness: brightness,
    primary: c.primary,
    onPrimary: c.onPrimary,
    primaryContainer: c.primarySoft,
    onPrimaryContainer: c.onPrimarySoft,
    secondary: c.primary,
    onSecondary: c.onPrimary,
    secondaryContainer: c.primarySoft,
    onSecondaryContainer: c.onPrimarySoft,
    error: c.fresh,
    onError: c.onFresh,
    surface: c.paper,
    onSurface: c.ink,
    onSurfaceVariant: c.inkSoft,
    surfaceContainerLowest: c.surface,
    surfaceContainerLow: c.surface,
    surfaceContainer: c.surface,
    surfaceContainerHigh: c.surface,
    surfaceContainerHighest: c.surfaceSunken,
    outline: c.lineStrong,
    outlineVariant: c.line,
    shadow: c.shadow,
    inverseSurface: c.ink,
    onInverseSurface: c.paper,
    inversePrimary: c.primarySoft,
  );

  final text = const TextTheme(
    displaySmall: AppType.wordmark,
    headlineMedium: AppType.headline,
    headlineSmall: AppType.section,
    titleLarge: AppType.title,
    titleMedium: AppType.title,
    bodyLarge: AppType.body,
    bodyMedium: AppType.body,
    labelLarge: AppType.label,
  ).apply(bodyColor: c.ink, displayColor: c.ink);

  return ThemeData(
    useMaterial3: true,
    brightness: brightness,
    colorScheme: scheme,
    extensions: [c],
    fontFamily: AppFonts.text,
    textTheme: text,
    scaffoldBackgroundColor: c.paper,
    canvasColor: c.paper,
    dividerColor: c.line,
    splashFactory: InkSparkle.splashFactory,
    visualDensity: VisualDensity.standard,
    materialTapTargetSize: MaterialTapTargetSize.padded,
    pageTransitionsTheme: const PageTransitionsTheme(
      builders: {
        TargetPlatform.android: CalmPageTransitionsBuilder(),
        TargetPlatform.iOS: CalmPageTransitionsBuilder(),
      },
    ),
    appBarTheme: AppBarTheme(
      backgroundColor: c.paper,
      foregroundColor: c.ink,
      elevation: 0,
      scrolledUnderElevation: 0,
      systemOverlayStyle: overlayStyleFor(c),
    ),
    progressIndicatorTheme: ProgressIndicatorThemeData(
      color: c.primary,
      linearTrackColor: c.line,
      circularTrackColor: c.line,
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: c.ink,
      contentTextStyle: AppType.bodyStrong.copyWith(color: c.paper),
      actionTextColor: c.isDark ? AppColors.light.primary : c.primarySoft,
      shape: const RoundedRectangleBorder(borderRadius: AppRadius.mdAll),
      insetPadding: const EdgeInsets.all(AppSpace.md),
    ),
    scrollbarTheme: ScrollbarThemeData(
      thickness: const WidgetStatePropertyAll(AppSpace.xs),
      radius: const Radius.circular(AppRadius.pill),
      thumbColor: WidgetStatePropertyAll(c.lineStrong),
    ),
  );
}

/// Status / navigation bar icons that match the paper background.
SystemUiOverlayStyle overlayStyleFor(AppColors c) {
  final iconBrightness = c.isDark ? Brightness.light : Brightness.dark;
  return SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: iconBrightness,
    statusBarBrightness: c.brightness,
    systemNavigationBarColor: c.paper,
    systemNavigationBarIconBrightness: iconBrightness,
    systemNavigationBarDividerColor: Colors.transparent,
  );
}

/// Screen change: a short fade with a slight rise. No sideways slide (it
/// suggests a "swipe back" gesture our users do not know) and nothing at all
/// when motion is reduced.
class CalmPageTransitionsBuilder extends PageTransitionsBuilder {
  const CalmPageTransitionsBuilder();

  static const double _rise = 0.03;

  @override
  Duration get transitionDuration => AppMotion.normal;

  @override
  Duration get reverseTransitionDuration => AppMotion.quick;

  @override
  Widget buildTransitions<T>(
    PageRoute<T> route,
    BuildContext context,
    Animation<double> animation,
    Animation<double> secondaryAnimation,
    Widget child,
  ) {
    if (context.reduceMotion) return child;
    final curved = CurvedAnimation(
      parent: animation,
      curve: AppMotion.curve,
      reverseCurve: Curves.easeIn,
    );
    return FadeTransition(
      opacity: curved,
      child: SlideTransition(
        position: Tween<Offset>(
          begin: const Offset(0, _rise),
          end: Offset.zero,
        ).animate(curved),
        child: child,
      ),
    );
  }
}
