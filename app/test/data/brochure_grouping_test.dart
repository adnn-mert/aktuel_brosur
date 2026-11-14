import 'dart:math';

import 'package:aktuel_brosur/data/data.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers.dart';

enum G { current, upcoming, past, hidden }

G _groupOf(Brochure b, DateTime today) {
  final groups = groupBrochures([b], today);
  if (groups.current.contains(b)) return G.current;
  if (groups.upcoming.contains(b)) return G.upcoming;
  if (groups.past.contains(b)) return G.past;
  return G.hidden;
}

void main() {
  final today = d(2026, 11, 13);

  group('groupBrochures rules', () {
    final cases = <(String, Brochure, G)>[
      ('single day today', brochure('a', from: today, to: today), G.current),
      (
        'valid_to == today',
        brochure('a', from: d(2026, 11, 7), to: today),
        G.current,
      ),
      (
        'valid_from == today',
        brochure('a', from: today, to: d(2026, 11, 19)),
        G.current,
      ),
      ('open end, started', brochure('a', from: d(2026, 11, 1)), G.current),
      ('open start, not ended', brochure('a', to: d(2026, 11, 20)), G.current),
      (
        'starts tomorrow',
        brochure('a', from: d(2026, 11, 14), to: d(2026, 11, 20)),
        G.upcoming,
      ),
      (
        'open end, starts later',
        brochure('a', from: d(2026, 11, 18)),
        G.upcoming,
      ),
      (
        'ended yesterday',
        brochure('a', from: d(2026, 11, 6), to: d(2026, 11, 12)),
        G.past,
      ),
      (
        'ended 28 days ago',
        brochure('a', from: d(2026, 10, 10), to: d(2026, 10, 16)),
        G.past,
      ),
      (
        'ended 29 days ago',
        brochure('a', from: d(2026, 10, 9), to: d(2026, 10, 15)),
        G.hidden,
      ),
      (
        'no dates, first seen today',
        brochure('a', firstSeen: today),
        G.current,
      ),
      (
        'no dates, first seen 14 days ago',
        brochure('a', firstSeen: d(2026, 10, 30)),
        G.current,
      ),
      (
        'no dates, first seen 15 days ago',
        brochure('a', firstSeen: d(2026, 10, 29)),
        G.past,
      ),
    ];
    for (final (name, b, expected) in cases) {
      test(name, () => expect(_groupOf(b, today), expected));
    }

    test('time of day in "today" is ignored', () {
      final b = brochure('a', from: d(2026, 11, 7), to: today);
      expect(_groupOf(b, DateTime(2026, 11, 13, 23, 59)), G.current);
    });
  });

  group('groupBrochures sorting', () {
    // Like live BİM data: many flyers valid at once, one of them running
    // for months. Rows are in the expected order, with the reason.
    final currentOrder = <(String, Brochure)>[
      (
        'newest start: this week\'s single-day flyer',
        brochure('today', title: 'Zeytin', from: today, to: today),
      ),
      (
        'same start, ends sooner',
        brochure('wed-short', title: 'Su', from: d(2026, 11, 11), to: today),
      ),
      (
        'same start and end: title order (Ç before S)',
        brochure(
          'wed-long-cay',
          title: 'Çay',
          from: d(2026, 11, 11),
          to: d(2026, 11, 17),
        ),
      ),
      (
        'same start and end: title order',
        brochure(
          'wed-long-sut',
          title: 'Süt',
          from: d(2026, 11, 11),
          to: d(2026, 11, 17),
        ),
      ),
      (
        'same start, open end goes after a known end',
        brochure('wed-open', title: 'Ayran', from: d(2026, 11, 11)),
      ),
      (
        'campaign running since March',
        brochure(
          'march',
          title: 'Aktüel',
          from: d(2026, 3, 24),
          to: d(2026, 12, 31),
        ),
      ),
      (
        'no valid_from: after every dated start',
        brochure('until-20', title: 'Bal', to: d(2026, 11, 20)),
      ),
      (
        'no dates at all: last (open end)',
        brochure('undated', title: 'Ekmek', firstSeen: today),
      ),
    ];

    test('current: newest start first, then sooner end, then title', () {
      final input = [for (final (_, b) in currentOrder.reversed) b];
      // Any input order gives the same result.
      for (final shuffled in [
        input,
        [...input]..shuffle(Random(7)),
      ]) {
        final groups = groupBrochures(shuffled, today);
        expect(
          groups.current.map((b) => b.id),
          currentOrder.map((row) => row.$2.id),
          reason: currentOrder.map((row) => row.$1).join('\n'),
        );
      }
    });

    test('upcoming by start ascending, ties by title', () {
      final groups = groupBrochures([
        brochure('u3', title: 'Zeytin', from: d(2026, 11, 18)),
        brochure('u2', from: d(2026, 11, 20)),
        brochure('u1', title: 'Çay', from: d(2026, 11, 18)),
      ], today);
      expect(groups.upcoming.map((b) => b.id), ['u1', 'u3', 'u2']);
    });

    test('past by end descending, ties by title', () {
      final groups = groupBrochures([
        brochure('p1', title: 'B', to: d(2026, 11, 1)),
        brochure('p2', title: 'Ş', to: d(2026, 11, 10)),
        brochure('p3', title: 'S', to: d(2026, 11, 10)),
      ], today);
      expect(groups.past.map((b) => b.id), ['p3', 'p2', 'p1']);
      expect(groups.isEmpty, isFalse);
    });

    test('empty input', () {
      expect(groupBrochures(const [], today).isEmpty, isTrue);
    });

    test('sample catalog groups', () {
      final catalog = sampleCatalog();
      final sok = groupBrochures(catalog.brochuresOf('sok'), sampleToday);
      expect(sok.current.map((b) => b.id), [
        'sok-2026-11-11-haftanin-firsatlari',
      ]);
      expect(sok.upcoming.map((b) => b.id), [
        'sok-2026-11-18-haftanin-firsatlari',
      ]);
      expect(sok.past.map((b) => b.id), ['sok-2026-10-28-haftanin-firsatlari']);
    });
  });

  group('orderChains', () {
    test('Turkish alphabetical order within equal sort_order', () {
      final names = [
        'Zeta',
        'Ünal',
        'Uğur',
        'Şok',
        'Sarı',
        'Öz',
        'Ozan',
        'İkbal',
        'Ilgaz',
        'Hakmar',
        'Gratis',
        'Ğ Market',
        'Dörtyol',
        'Çağrı',
        'Cem',
      ];
      final chains = [
        for (final (i, n) in names.indexed) chain('c$i', name: n),
      ];
      expect(orderChains(chains, const {}).map((c) => c.name), [
        'Cem',
        'Çağrı',
        'Dörtyol',
        'Gratis',
        'Ğ Market',
        'Hakmar',
        'Ilgaz',
        'İkbal',
        'Ozan',
        'Öz',
        'Sarı',
        'Şok',
        'Uğur',
        'Ünal',
        'Zeta',
      ]);
    });

    test('favourites first, then sort_order, then name', () {
      final chains = [
        chain('sok', name: 'Şok', sortOrder: 30),
        chain('bim', name: 'BİM', sortOrder: 10),
        chain('a101', name: 'A101', sortOrder: 20),
        chain('migros', name: 'Migros', sortOrder: 40),
        chain('watsons', name: 'Watsons', sortOrder: 20),
      ];
      expect(orderChains(chains, const {}).map((c) => c.id), [
        'bim',
        'a101',
        'watsons',
        'sok',
        'migros',
      ]);
      expect(orderChains(chains, const {'migros', 'sok'}).map((c) => c.id), [
        'sok',
        'migros',
        'bim',
        'a101',
        'watsons',
      ]);
    });

    test('compareTurkish is case-insensitive', () {
      // A plain code-unit comparison would put 'B' before 'a'.
      expect(compareTurkish('ali', 'Bora'), lessThan(0));
      expect(compareTurkish('ılık', 'İlik'), lessThan(0));
      expect(compareTurkish('Çam', 'dut'), lessThan(0));
      // Same letters, different case: still a total order.
      expect(compareTurkish('bim', 'BİM'), isNot(0));
    });
  });

  group('chainSummary', () {
    test('sample chains', () {
      final catalog = sampleCatalog();
      ChainSummary summary(String id) =>
          chainSummary(catalog.chainById(id)!, catalog.brochures, sampleToday);

      final bim = summary('bim');
      expect(bim.currentCount, 1);
      expect(bim.upcomingCount, 1);
      expect(bim.pastCount, 1);
      expect(bim.isNew, isTrue);
      expect(bim.latestFirstSeen, DateTime.utc(2026, 11, 13, 8, 58, 41));
      expect(bim.isStale, isFalse);
      expect(bim.hasBrochures, isTrue);

      final watsons = summary('watsons');
      expect(watsons.currentCount, 1);
      expect(watsons.isNew, isFalse);
      expect(watsons.isStale, isTrue);

      final a101 = summary('a101');
      expect(a101.isWebView, isTrue);
      expect(a101.hasBrochures, isFalse);
      expect(a101.latestFirstSeen, isNull);
      expect(a101.isNew, isFalse);
    });

    test('"new" means first seen today or yesterday', () {
      final c = chain('bim');
      bool isNew(DateTime firstSeen) => chainSummary(c, [
        brochure(
          'x',
          from: d(2026, 11, 10),
          to: d(2026, 11, 20),
          firstSeen: firstSeen,
        ),
      ], today).isNew;

      expect(isNew(today), isTrue);
      expect(isNew(d(2026, 11, 12)), isTrue);
      expect(isNew(d(2026, 11, 11)), isFalse);
    });

    test('a past brochure never makes the chain "new"', () {
      final summary = chainSummary(chain('bim'), [
        brochure('x', to: d(2026, 11, 12), firstSeen: today),
      ], today);
      expect(summary.isNew, isFalse);
      expect(summary.pastCount, 1);
    });

    test('ignores other chains', () {
      final summary = chainSummary(chain('bim'), [
        brochure('x', chainId: 'sok', from: today, to: today),
      ], today);
      expect(summary.hasBrochures, isFalse);
    });
  });

  group('formatDateRange', () {
    String f(DateTime? from, DateTime? to, {String? label}) =>
        formatDateRange(from, to, today, dateLabel: label);

    test('same month', () {
      expect(f(d(2026, 11, 13), d(2026, 11, 19)), '13–19 Kasım');
    });

    test('month changes', () {
      expect(f(d(2026, 10, 22), d(2026, 11, 4)), '22 Ekim – 4 Kasım');
    });

    test('single day shows the weekday', () {
      expect(f(d(2026, 11, 13), d(2026, 11, 13)), '13 Kasım Cuma');
      expect(f(d(2026, 11, 16), d(2026, 11, 16)), '16 Kasım Pazartesi');
      expect(f(d(2026, 11, 15), d(2026, 11, 15)), '15 Kasım Pazar');
    });

    test('no dates falls back to date_label, then empty', () {
      expect(f(null, null, label: ' Kasım 2026 '), 'Kasım 2026');
      expect(f(null, null), '');
    });

    test('structured dates win over date_label', () {
      expect(
        f(d(2026, 11, 13), d(2026, 11, 19), label: 'Haftanın Yıldızları'),
        '13–19 Kasım',
      );
    });

    test('year is added when it is not this year', () {
      expect(f(d(2027, 1, 5), d(2027, 1, 11)), '5–11 Ocak 2027');
      expect(f(d(2025, 10, 22), d(2025, 11, 4)), '22 Ekim – 4 Kasım 2025');
      expect(f(d(2025, 11, 13), d(2025, 11, 13)), '13 Kasım 2025 Perşembe');
    });

    test('range crossing New Year shows both years', () {
      expect(f(d(2026, 12, 29), d(2027, 1, 4)), '29 Aralık 2026 – 4 Ocak 2027');
    });

    test('open-ended ranges', () {
      expect(f(d(2026, 11, 13), null), "13 Kasım'dan itibaren");
      expect(f(d(2026, 9, 1), null), "1 Eylül'den itibaren");
      expect(f(d(2026, 4, 1), null), "1 Nisan'dan itibaren");
      expect(f(null, d(2026, 11, 19)), "19 Kasım'a kadar");
      expect(f(null, d(2026, 10, 3)), "3 Ekim'e kadar");
      expect(f(d(2027, 1, 2), null), '2 Ocak 2027 tarihinden itibaren');
      expect(f(null, d(2027, 1, 2)), '2 Ocak 2027 tarihine kadar');
    });

    test('formatBrochureDates uses the brochure fields', () {
      final catalog = sampleCatalog();
      expect(
        formatBrochureDates(catalog.brochureById('migros-909')!, sampleToday),
        '29 Ekim – 11 Kasım',
      );
    });
  });
}
