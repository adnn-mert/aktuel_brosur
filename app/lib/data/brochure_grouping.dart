/// Pure, clock-free logic that turns catalog data into what screens show.
/// Every function takes `today` explicitly so it can be tested for any date.
library;

import 'package:intl/date_symbol_data_local.dart' show dateTimeSymbolMap;
import 'package:intl/date_symbols.dart';

import 'models/brochure.dart';
import 'models/chain.dart';

/// Brochures without any dates count as current for this long after the
/// scraper first saw them.
const int undatedCurrentDays = 14;

/// Ended brochures stay visible under "Geçmiş" for this many days.
const int pastVisibleDays = 28;

/// A chain is flagged "new" when a current/upcoming brochure was first seen
/// today or yesterday.
const int newBadgeDays = 2;

/// Strips the time: local midnight of [d]'s calendar day.
DateTime dateOnly(DateTime d) => DateTime(d.year, d.month, d.day);

// Day arithmetic in UTC so a DST switch can never make a "day" 23 hours.
int _dayNumber(DateTime d) =>
    DateTime.utc(d.year, d.month, d.day).millisecondsSinceEpoch ~/
    Duration.millisecondsPerDay;

/// Whole calendar days from [from] to [to] (negative if [to] is earlier).
int daysBetween(DateTime from, DateTime to) =>
    _dayNumber(to) - _dayNumber(from);

/// The calendar day (device time zone) on which [b] was first seen.
DateTime _firstSeenDay(Brochure b) => dateOnly(b.firstSeen.toLocal());

/// A chain's brochures split the way the market screen shows them.
class BrochureGroups {
  const BrochureGroups({
    this.current = const [],
    this.upcoming = const [],
    this.past = const [],
  });

  /// Valid today ("Bu hafta"), newest start first; equal starts: the one
  /// ending sooner first (open end last), then title. Brochures without a
  /// start day come last.
  final List<Brochure> current;

  /// Starting after today ("Gelecek hafta"), sorted by start day, then title.
  final List<Brochure> upcoming;

  /// Ended within the last [pastVisibleDays] days ("Geçmiş"), most recently
  /// ended first. Older brochures are dropped entirely.
  final List<Brochure> past;

  bool get isEmpty => current.isEmpty && upcoming.isEmpty && past.isEmpty;

  @override
  String toString() =>
      'BrochureGroups(current: $current, upcoming: $upcoming, past: $past)';
}

enum _Bucket { current, upcoming, past, hidden }

_Bucket _bucketOf(Brochure b, DateTime today) {
  final from = b.validFrom;
  final to = b.validTo;
  if (from == null && to == null) {
    return daysBetween(_firstSeenDay(b), today) <= undatedCurrentDays
        ? _Bucket.current
        : _Bucket.past;
  }
  if (from != null && daysBetween(today, from) > 0) return _Bucket.upcoming;
  if (to == null || daysBetween(to, today) <= 0) return _Bucket.current;
  return daysBetween(to, today) <= pastVisibleDays
      ? _Bucket.past
      : _Bucket.hidden;
}

int _byTitle(Brochure a, Brochure b) {
  final c = compareTurkish(a.title, b.title);
  return c != 0 ? c : a.id.compareTo(b.id);
}

List<Brochure> _sorted(
  Iterable<Brochure> items,
  DateTime Function(Brochure) key, {
  required bool descending,
}) {
  final list = items.toList();
  list.sort((a, b) {
    var c = key(a).compareTo(key(b));
    if (descending) c = -c;
    return c != 0 ? c : _byTitle(a, b);
  });
  return List.unmodifiable(list);
}

// Orders two optional days; a missing day sorts after any present one.
int _compareDays(DateTime? a, DateTime? b, {required bool descending}) {
  if (a == null || b == null) {
    if (a == b) return 0;
    return a == null ? 1 : -1;
  }
  final c = daysBetween(b, a).sign;
  return descending ? -c : c;
}

// "Bu hafta": what started most recently is what the reader came for. A
// chain like BİM has ~10 valid flyers at once, and one running from March
// to December must not push this week's flyer to the bottom.
List<Brochure> _sortedCurrent(Iterable<Brochure> items) {
  final list = items.toList();
  list.sort((a, b) {
    var c = _compareDays(a.validFrom, b.validFrom, descending: true);
    if (c != 0) return c;
    c = _compareDays(a.validTo, b.validTo, descending: false);
    return c != 0 ? c : _byTitle(a, b);
  });
  return List.unmodifiable(list);
}

/// Splits [brochures] into current / upcoming / past relative to [today]
/// (only its calendar day is used).
///
/// * current: `valid_from <= today <= valid_to`; an open end (`valid_to`
///   null) counts as still valid; with no dates at all, current when first
///   seen within [undatedCurrentDays] days, otherwise past.
/// * upcoming: `valid_from > today`.
/// * past: `valid_to < today` and ended at most [pastVisibleDays] days ago;
///   older brochures are left out.
BrochureGroups groupBrochures(List<Brochure> brochures, DateTime today) {
  final day = dateOnly(today);
  final buckets = <_Bucket, List<Brochure>>{};
  for (final b in brochures) {
    buckets.putIfAbsent(_bucketOf(b, day), () => []).add(b);
  }
  DateTime startKey(Brochure b) => b.validFrom ?? _firstSeenDay(b);
  DateTime endKey(Brochure b) => b.validTo ?? _firstSeenDay(b);
  return BrochureGroups(
    current: _sortedCurrent(buckets[_Bucket.current] ?? const []),
    upcoming: _sorted(
      buckets[_Bucket.upcoming] ?? const [],
      startKey,
      descending: false,
    ),
    past: _sorted(buckets[_Bucket.past] ?? const [], endKey, descending: true),
  );
}

// Turkish alphabet order, with the letters Turkish lacks (q, w, x) and
// circumflex vowels slotted where Turkish dictionaries put them.
const String _turkishOrder = '0123456789aâbcçdefgğhıiîjklmnoöpqrsştuüûvwxyz';
final Map<int, int> _turkishRank = {
  for (final (i, rune) in _turkishOrder.runes.indexed) rune: i,
};

String _turkishLower(String s) =>
    s.replaceAll('I', 'ı').replaceAll('İ', 'i').toLowerCase();

/// Case-insensitive comparison in Turkish alphabetical order
/// (… C < Ç < D …, G < Ğ, I < İ, O < Ö, S < Ş, U < Ü). Characters outside
/// the alphabet sort after it by code point; exact ties fall back to a plain
/// comparison so the order is total.
int compareTurkish(String a, String b) {
  final ra = _turkishLower(a).runes.toList();
  final rb = _turkishLower(b).runes.toList();
  final n = ra.length < rb.length ? ra.length : rb.length;
  for (var i = 0; i < n; i++) {
    if (ra[i] == rb[i]) continue;
    final ka = _turkishRank[ra[i]] ?? (_turkishOrder.length + ra[i]);
    final kb = _turkishRank[rb[i]] ?? (_turkishOrder.length + rb[i]);
    if (ka != kb) return ka.compareTo(kb);
  }
  if (ra.length != rb.length) return ra.length.compareTo(rb.length);
  return a.compareTo(b);
}

/// Home-screen order: favourites first, then `sort_order`, then name in
/// Turkish alphabetical order.
List<Chain> orderChains(List<Chain> chains, Set<String> favoriteIds) {
  final list = chains.toList();
  list.sort((a, b) {
    final fa = favoriteIds.contains(a.id);
    final fb = favoriteIds.contains(b.id);
    if (fa != fb) return fa ? -1 : 1;
    final c = a.sortOrder.compareTo(b.sortOrder);
    if (c != 0) return c;
    final n = compareTurkish(a.name, b.name);
    return n != 0 ? n : a.id.compareTo(b.id);
  });
  return List.unmodifiable(list);
}

/// What a home-screen chain card needs to know.
class ChainSummary {
  const ChainSummary({
    required this.chain,
    required this.currentCount,
    required this.upcomingCount,
    required this.pastCount,
    required this.latestFirstSeen,
    required this.isNew,
  });

  final Chain chain;

  /// Brochures valid today.
  final int currentCount;

  /// Brochures that start after today.
  final int upcomingCount;

  /// Visible past brochures (ended within [pastVisibleDays] days).
  final int pastCount;

  /// `first_seen` (UTC) of the newest visible brochure, if any.
  final DateTime? latestFirstSeen;

  /// A current or upcoming brochure was first seen today or yesterday.
  final bool isNew;

  /// The chain's scraper failed last time; data may be outdated.
  bool get isStale => chain.isStale;

  /// Web-view chains have no brochures; open [Chain.webUrl] instead.
  bool get isWebView => chain.isWebView;

  /// Anything to show on the market screen.
  bool get hasBrochures => currentCount + upcomingCount + pastCount > 0;

  @override
  bool operator ==(Object other) =>
      other is ChainSummary &&
      other.chain == chain &&
      other.currentCount == currentCount &&
      other.upcomingCount == upcomingCount &&
      other.pastCount == pastCount &&
      other.latestFirstSeen == latestFirstSeen &&
      other.isNew == isNew;

  @override
  int get hashCode => Object.hash(
    chain,
    currentCount,
    upcomingCount,
    pastCount,
    latestFirstSeen,
    isNew,
  );

  @override
  String toString() =>
      'ChainSummary(${chain.id}, current: $currentCount, '
      'upcoming: $upcomingCount, past: $pastCount, new: $isNew)';
}

/// Builds the card summary of [chain]. [brochures] may contain other chains'
/// brochures; they are ignored.
ChainSummary chainSummary(
  Chain chain,
  List<Brochure> brochures,
  DateTime today,
) {
  final groups = groupBrochures(
    brochures.where((b) => b.chainId == chain.id).toList(),
    today,
  );
  final visible = [...groups.current, ...groups.upcoming, ...groups.past];
  DateTime? latest;
  for (final b in visible) {
    if (latest == null || b.firstSeen.isAfter(latest)) latest = b.firstSeen;
  }
  final day = dateOnly(today);
  final isNew = [
    ...groups.current,
    ...groups.upcoming,
  ].any((b) => daysBetween(_firstSeenDay(b), day) < newBadgeDays);
  return ChainSummary(
    chain: chain,
    currentCount: groups.current.length,
    upcomingCount: groups.upcoming.length,
    pastCount: groups.past.length,
    latestFirstSeen: latest,
    isNew: isNew,
  );
}

final DateSymbols _tr = dateTimeSymbolMap()['tr']!;

String _month(DateTime d) => _tr.MONTHS[d.month - 1];

// DateSymbols.WEEKDAYS starts on Sunday; DateTime.weekday is 1 = Monday.
String _weekday(DateTime d) => _tr.WEEKDAYS[d.weekday % 7];

// Turkish case suffixes for "from <month>" / "until <month>" (vowel harmony
// and consonant hardening depend on the month name, so they are listed).
const List<String> _fromSuffix = [
  "'tan", "'tan", "'tan", "'dan", "'tan", "'dan", //
  "'dan", "'tan", "'den", "'den", "'dan", "'tan",
];
const List<String> _untilSuffix = [
  "'a", "'a", "'a", "'a", "'a", "'a", //
  "'a", "'a", "'e", "'e", "'a", "'a",
];

/// Human date range for a brochure, in Turkish:
///
/// * same day: `13 Kasım Cuma`
/// * same month: `13–19 Kasım`
/// * different months: `22 Ekim – 4 Kasım`
/// * not this year: year appended (`13–19 Kasım 2027`); a range crossing
///   New Year shows both years (`29 Aralık 2026 – 4 Ocak 2027`)
/// * open start/end: `13 Kasım'dan itibaren` / `19 Kasım'a kadar`
/// * no dates: [dateLabel] (trimmed), else an empty string.
String formatDateRange(
  DateTime? validFrom,
  DateTime? validTo,
  DateTime today, {
  String? dateLabel,
}) {
  final from = validFrom == null ? null : dateOnly(validFrom);
  final to = validTo == null ? null : dateOnly(validTo);
  final year = today.year;

  if (from == null && to == null) return dateLabel?.trim() ?? '';

  if (from != null && to != null) {
    final yearSuffix = (from.year == year && to.year == year)
        ? ''
        : ' ${to.year}';
    if (from == to) {
      final y = from.year == year ? '' : ' ${from.year}';
      return '${from.day} ${_month(from)}$y ${_weekday(from)}';
    }
    if (from.year != to.year) {
      return '${from.day} ${_month(from)} ${from.year} – '
          '${to.day} ${_month(to)} ${to.year}';
    }
    if (from.month == to.month) {
      return '${from.day}–${to.day} ${_month(to)}$yearSuffix';
    }
    return '${from.day} ${_month(from)} – ${to.day} ${_month(to)}$yearSuffix';
  }

  if (from != null) {
    if (from.year != year) {
      return '${from.day} ${_month(from)} ${from.year} tarihinden itibaren';
    }
    return '${from.day} ${_month(from)}${_fromSuffix[from.month - 1]} '
        'itibaren';
  }

  final end = to!;
  if (end.year != year) {
    return '${end.day} ${_month(end)} ${end.year} tarihine kadar';
  }
  return '${end.day} ${_month(end)}${_untilSuffix[end.month - 1]} kadar';
}

/// [formatDateRange] applied to a brochure's own fields.
String formatBrochureDates(Brochure brochure, DateTime today) =>
    formatDateRange(
      brochure.validFrom,
      brochure.validTo,
      today,
      dateLabel: brochure.dateLabel,
    );
