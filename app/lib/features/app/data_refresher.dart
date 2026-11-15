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
/// * Showing the saved copy because the network was unreachable: fetched
///   again at once when the app comes back, and every
///   [offlineRetryInterval] while it stays in the foreground, until a
///   download succeeds. Nothing runs in the background.
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
  Timer? _offlineRetry;

  /// The calendar day the screens were last built for.
  late DateTime _shownDay;

  /// Visible on screen (resumed or inactive). Retrying while hidden would
  /// only spend battery on a screen nobody reads.
  late bool _inForeground;

  /// A download started here has not finished yet.
  bool _refreshing = false;

  @override
  void initState() {
    super.initState();
    _shownDay = ref.read(clockProvider).today();
    _inForeground = switch (WidgetsBinding.instance.lifecycleState) {
      null || AppLifecycleState.resumed || AppLifecycleState.inactive => true,
      _ => false,
    };
    _lifecycle = AppLifecycleListener(
      onResume: _onResume,
      onShow: () => _setForeground(true),
      onHide: () => _setForeground(false),
    );
    // Catches every way the catalog turns stale (an offline cold start, a
    // pull to refresh, a quiet refresh) or fresh again.
    ref.listenManual(
      catalogProvider,
      (_, _) => _syncOfflineRetry(),
      fireImmediately: true,
    );
    _scheduleMidnight();
  }

  @override
  void dispose() {
    _midnight?.cancel();
    _offlineRetry?.cancel();
    _lifecycle.dispose();
    super.dispose();
  }

  void _onResume() {
    _inForeground = true;
    final now = ref.read(clockProvider).now();
    _updateDay(now);
    // The timer may have been frozen with the process; aim it again.
    _scheduleMidnight();
    _refreshCatalogIfNeeded(now);
  }

  void _setForeground(bool value) {
    _inForeground = value;
    _syncOfflineRetry();
  }

  void _updateDay(DateTime now) {
    if (!dayChanged(_shownDay, now)) return;
    _shownDay = dateOnly(now);
    ref.invalidate(clockProvider);
  }

  void _refreshCatalogIfNeeded(DateTime now) {
    final catalog = ref.read(catalogProvider);
    // The first load (or a retry after it failed) is still running; a
    // second download would only race it.
    if (catalog.isLoading && !catalog.hasValue) return;
    final shown = catalog.value;
    if (!shouldRefreshCatalog(
      shown?.fetchedAt,
      now,
      offline: shown?.isStale ?? false,
    )) {
      return;
    }
    unawaited(_refreshCatalog());
  }

  /// refresh() keeps the shown data, never throws, and shares a download
  /// already running (pull to refresh); its outcome is deliberately unused.
  Future<void> _refreshCatalog() async {
    _cancelOfflineRetry();
    _refreshing = true;
    try {
      await ref.read(catalogProvider.notifier).refresh();
    } finally {
      _refreshing = false;
    }
    // A failed retry usually serves the same saved copy, which Riverpod
    // does not report as a change, so the listener alone would not re-arm.
    if (mounted) _syncOfflineRetry();
  }

  /// Arms the offline retry when the saved copy is shown in the foreground,
  /// and disarms it otherwise.
  void _syncOfflineRetry() {
    final offline = ref.read(catalogProvider).value?.isStale ?? false;
    if (!offline || !_inForeground) {
      _cancelOfflineRetry();
      return;
    }
    if (_offlineRetry != null || _refreshing) return;
    _offlineRetry = Timer(offlineRetryInterval, () {
      _offlineRetry = null;
      if (mounted) unawaited(_refreshCatalog());
    });
  }

  void _cancelOfflineRetry() {
    _offlineRetry?.cancel();
    _offlineRetry = null;
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
