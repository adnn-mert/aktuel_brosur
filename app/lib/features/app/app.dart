import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import '../../design/theme.dart';
import '../../design/typography.dart';
import '../../l10n/app_localizations.dart';
import '../splash/splash_gate.dart';

/// Root widget of Çarşı Pazar.
class CarsiPazarApp extends StatelessWidget {
  const CarsiPazarApp({super.key, this.showSplash = true});

  /// Tests switch the splash off to land on the home screen directly.
  final bool showSplash;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      onGenerateTitle: (context) => AppLocalizations.of(context).appTitle,
      debugShowCheckedModeBanner: false,
      locale: const Locale('tr'),
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      theme: buildAppTheme(Brightness.light),
      darkTheme: buildAppTheme(Brightness.dark),
      themeMode: ThemeMode.system,
      builder: (context, child) {
        // Honour the system font size, up to the factor the layouts are
        // built for.
        final media = MediaQuery.of(context);
        return MediaQuery(
          data: media.copyWith(
            textScaler: media.textScaler.clamp(maxScaleFactor: maxTextScale),
          ),
          child: child ?? const SizedBox.shrink(),
        );
      },
      home: SplashGate(showSplash: showSplash),
    );
  }
}
