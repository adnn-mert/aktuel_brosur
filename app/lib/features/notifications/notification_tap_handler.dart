import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/data.dart';
import '../app/navigation.dart';

/// Where a tapped "new brochure" notification leads.
///
/// * The brochure itself, when the notification names one that is in the
///   catalog (and belongs to that market): that is what the message was
///   about. It opens directly on top of whatever was on screen; no market
///   screen is slipped in underneath, so "Geri" returns to where the user
///   was (DESIGN.md, principle 4).
/// * Otherwise the market, exactly as its home card would open it
///   ([openChain]: market screen, its only brochure, or its web page).
/// * An unknown market, or no catalog at all (offline first launch), leaves
///   the user on the home screen, which explains the situation itself.
///
/// Wraps the first route of the app so it is listening from the first frame
/// (a tap that launched the app arrives right away).
///
/// Every [NotificationTap] is its own event (no value equality), so tapping
/// a notification for the same brochure again opens it again.
class NotificationTapHandler extends ConsumerStatefulWidget {
  const NotificationTapHandler({super.key, required this.child});

  final Widget child;

  @override
  ConsumerState<NotificationTapHandler> createState() =>
      _NotificationTapHandlerState();
}

class _NotificationTapHandlerState
    extends ConsumerState<NotificationTapHandler> {
  @override
  void initState() {
    super.initState();
    ref.listenManual<AsyncValue<NotificationTap>>(notificationTapProvider, (
      previous,
      next,
    ) {
      final tap = next.value;
      if (tap == null || identical(tap, previous?.value)) return;
      _open(tap);
    }, fireImmediately: true);
    // Also starts the notification switch at launch, so its status is known
    // by the time the first star is placed and it keeps the favourite
    // markets' subscriptions in step even while no screen shows it.
    ref.listenManual(notificationsProvider, (_, _) {});
  }

  Future<void> _open(NotificationTap tap) async {
    final Catalog catalog;
    try {
      catalog = (await ref.read(catalogProvider.future)).catalog;
    } on Object {
      return;
    }
    if (!mounted) return;
    final chain = catalog.chainById(tap.chainId);
    if (chain == null) return;
    final brochureId = tap.brochureId;
    final brochure = brochureId == null
        ? null
        : catalog.brochureById(brochureId);
    if (brochure != null && brochure.chainId == chain.id) {
      await openBrochure(context, brochure.id);
    } else {
      await openChain(context, ref, chain);
    }
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
