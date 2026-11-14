import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/data.dart';

/// Keeps "today" and the catalog current while the app lives for days in
/// the background. Shows nothing itself; the decisions are the pure
/// functions in `data/freshness.dart`.
///
/// * Back in the foreground: a new calendar day regroups the brochures and
///   updates "Bugün …"; a catalog older than [catalogMaxAge] is fetched
///   again quietly (the shown data stays, a failure is not reported).
/// * Open across midnight: the day is updated at midnight.
class DayAndCatalogRefresher extends ConsumerStatefulWidget {
  const DayAndCatalogRefresher({super.key, required this.child});

  final Widget child;

  @override
  ConsumerState<DayAndCatalogRefresher> createState() =>
      _DayAndCatalogRefresherState();
}

class _DayAndCatalogRefresherState
    extends ConsumerState<DayAndCatalogRefresher> {
  late final AppLifecycleListener _lifecycle;
  Timer? _midnight;

  /// The calendar day the screens were last built for.
  late DateTime _shownDay;

  @override
  void initState() {
    super.initState();
    _shownDay = ref.read(clockProvider).today();
    _lifecycle = AppLifecycleListener(onResume: _onResume);
    _scheduleMidnight();
  }

  @override
  void dispose() {
    _midnight?.cancel();
    _lifecycle.dispose();
    super.dispose();
  }

  void _onResume() {
    final now = ref.read(clockProvider).now();
    _updateDay(now);
    // The timer may have been frozen with the process; aim it again.
    _scheduleMidnight();
    _refreshCatalogIfOld(now);
  }

  void _updateDay(DateTime now) {
    if (!dayChanged(_shownDay, now)) return;
    _shownDay = dateOnly(now);
    ref.invalidate(clockProvider);
  }

  void _refreshCatalogIfOld(DateTime now) {
    final catalog = ref.read(catalogProvider);
    // The first load (or a retry after it failed) is still running; a
    // second download would only race it.
    if (catalog.isLoading && !catalog.hasValue) return;
    if (!shouldRefreshCatalog(catalog.value?.fetchedAt, now)) return;
    // refresh() keeps the shown data, never throws, and shares a download
    // already running (pull to refresh); its outcome is deliberately unused.
    unawaited(ref.read(catalogProvider.notifier).refresh());
  }

  void _scheduleMidnight() {
    _midnight?.cancel();
    final wait = untilNextDay(ref.read(clockProvider).now());
    _midnight = Timer(wait, () {
      if (!mounted) return;
      _updateDay(ref.read(clockProvider).now());
      _scheduleMidnight();
    });
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
