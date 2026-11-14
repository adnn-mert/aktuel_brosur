import 'package:aktuel_brosur/data/data.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final now = DateTime(2026, 11, 14, 9, 30);

  group('shouldRefreshCatalog', () {
    final cases = <(String, DateTime?, bool)>[
      ('never fetched', null, true),
      ('fetched just now', now, false),
      ('29 minutes ago', now.subtract(const Duration(minutes: 29)), false),
      ('exactly 30 minutes ago', now.subtract(catalogMaxAge), false),
      ('31 minutes ago', now.subtract(const Duration(minutes: 31)), true),
      ('yesterday', now.subtract(const Duration(days: 1)), true),
      // The device clock was moved back after the last fetch.
      ('in the future', now.add(const Duration(hours: 2)), true),
    ];
    for (final (name, fetchedAt, expected) in cases) {
      test(name, () => expect(shouldRefreshCatalog(fetchedAt, now), expected));
    }

    test('a UTC fetch time is compared as the same instant', () {
      final fetchedAt = now.subtract(const Duration(minutes: 10)).toUtc();
      expect(shouldRefreshCatalog(fetchedAt, now), isFalse);
    });
  });

  group('dayChanged', () {
    final cases = <(String, DateTime, DateTime, bool)>[
      (
        'same day, morning to night',
        DateTime(2026, 11, 14, 0, 0),
        DateTime(2026, 11, 14, 23, 59, 59),
        false,
      ),
      (
        'one second past midnight',
        DateTime(2026, 11, 14, 23, 59, 59),
        DateTime(2026, 11, 15, 0, 0, 0),
        true,
      ),
      (
        'next morning',
        DateTime(2026, 11, 14, 21),
        DateTime(2026, 11, 15, 8),
        true,
      ),
      (
        'same day number, next month',
        DateTime(2026, 11, 14),
        DateTime(2026, 12, 14),
        true,
      ),
      ('New Year', DateTime(2026, 12, 31, 23), DateTime(2027, 1, 1, 1), true),
      (
        'clock moved back a day',
        DateTime(2026, 11, 15, 9),
        DateTime(2026, 11, 14, 9),
        true,
      ),
    ];
    for (final (name, previous, current, expected) in cases) {
      test(name, () => expect(dayChanged(previous, current), expected));
    }
  });

  group('untilNextDay', () {
    test('counts to the next local midnight', () {
      expect(
        untilNextDay(DateTime(2026, 11, 14, 23, 59)),
        const Duration(minutes: 1),
      );
      expect(
        untilNextDay(DateTime(2026, 11, 14, 9, 30)),
        const Duration(hours: 14, minutes: 30),
      );
    });

    test('at midnight waits a whole day, never zero', () {
      final wait = untilNextDay(DateTime(2026, 11, 14));
      expect(wait, greaterThan(Duration.zero));
      expect(
        DateTime(2026, 11, 14).add(wait).day,
        15,
        reason: 'lands on the next calendar day',
      );
    });

    test('crosses month and year ends', () {
      expect(
        untilNextDay(DateTime(2026, 12, 31, 22)),
        const Duration(hours: 2),
      );
    });
  });
}
