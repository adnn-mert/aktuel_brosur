import 'package:aktuel_brosur/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets('app opens with the bundled sample and lists chains', (
    tester,
  ) async {
    SharedPreferences.setMockInitialValues({});
    // Tall surface so every chain row is built without scrolling.
    tester.view.physicalSize = const Size(800, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(const ProviderScope(child: AktuelBrosurApp()));
    await tester.pumpAndSettle();

    expect(find.text('Marketler'), findsOneWidget);
    for (final name in [
      'BİM',
      'A101',
      'Şok',
      'Migros',
      'Watsons',
      'CarrefourSA',
      'Gratis',
    ]) {
      expect(find.text(name), findsOneWidget, reason: name);
    }
  });
}
