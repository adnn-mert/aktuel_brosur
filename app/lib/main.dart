// PLACEHOLDER — to be replaced by the designer.
//
// Bare app shell that only proves the data layer works end to end. Keep the
// ProviderScope and the localization setup; replace everything visual.

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'features/placeholder/chain_list_screen.dart';
import 'l10n/app_localizations.dart';

void main() {
  runApp(const ProviderScope(child: AktuelBrosurApp()));
}

class AktuelBrosurApp extends StatelessWidget {
  const AktuelBrosurApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      onGenerateTitle: (context) => AppLocalizations.of(context).appTitle,
      locale: const Locale('tr'),
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: const ChainListScreen(),
    );
  }
}
