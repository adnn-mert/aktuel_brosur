/// Pure decisions about when shown data has gone out of date. The app root
/// asks these when the app comes back to the foreground and at midnight;
/// every function takes `now` explicitly so it can be tested for any time.
library;

import 'brochure_grouping.dart' show dateOnly;

/// A catalog older than this is fetched again when the app resumes. The
/// scraper publishes three times a day, so half an hour keeps the shown
/// data close to the published one without a download on every glance.
const Duration catalogMaxAge = Duration(minutes: 30);

/// Whether the catalog last fetched at [lastFetchedAt] should be fetched
/// again at [now]. A catalog never fetched (null) should. A fetch time in
/// the future means the device clock was moved back; trusting it could
/// postpone the next refresh by days, so that counts as out of date too.
bool shouldRefreshCatalog(DateTime? lastFetchedAt, DateTime now) {
  if (lastFetchedAt == null) return true;
  final age = now.difference(lastFetchedAt);
  return age.isNegative || age > catalogMaxAge;
}

/// Whether [now] falls on another calendar day (device time zone) than
/// [previous].
bool dayChanged(DateTime previous, DateTime now) {
  final a = previous.toLocal();
  final b = now.toLocal();
  return a.year != b.year || a.month != b.month || a.day != b.day;
}

/// Time from [now] to the next local midnight. Never zero, so a timer set
/// with it cannot spin.
Duration untilNextDay(DateTime now) {
  final local = now.toLocal();
  final today = dateOnly(local);
  // DateTime's constructor normalises day overflow and lands on local
  // midnight even across a DST switch, where a fixed 24 hours would not.
  final next = DateTime(today.year, today.month, today.day + 1);
  final wait = next.difference(local);
  return wait > Duration.zero ? wait : const Duration(seconds: 1);
}
