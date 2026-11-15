/// The notification offer: one window that says in a plain sentence what
/// will happen before the phone's own permission window, and the switching
/// on and off around it. See DESIGN.md, section 16.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/data.dart';
import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../../design/typography.dart';
import '../../design/widgets/app_buttons.dart';
import '../../design/widgets/feedback.dart';
import '../../l10n/app_localizations.dart';
import 'notification_offer_store.dart';

/// The current notification status; null while it is not known yet (or could
/// not be read), which the interface treats like
/// [NotificationsStatus.unavailable]: nothing is shown.
NotificationsStatus? notificationStatusOf(WidgetRef ref) =>
    ref.read(notificationsProvider).value?.status;

/// The status once it is known. A star must not wait long for its "moved to
/// the top" message, so after [_statusWait] the answer is "unknown" (and no
/// offer is made; the home control remains).
Future<NotificationsStatus?> _settledStatus(WidgetRef ref) async {
  try {
    final state = await ref
        .read(notificationsProvider.future)
        .timeout(_statusWait);
    return state.status;
  } on Object {
    return null;
  }
}

const Duration _statusWait = Duration(seconds: 2);

/// [names] as one phrase for a sentence: "Şok", "Şok ve BİM", "Şok, BİM ve
/// Migros"; more than three become "Sık baktığınız 5 market".
String chainNamesPhrase(AppLocalizations l10n, List<String> names) =>
    switch (names) {
      [final only] => only,
      [final first, final second] => l10n.nameListTwo(first, second),
      [final first, final second, final third] => l10n.nameListThree(
        first,
        second,
        third,
      ),
      _ => l10n.favoriteChainsCount(names.length),
    };

/// Offers notifications right after the user starred their very first
/// market. Shown at most once, ever, and only while notifications are off.
/// Returns true when the window was shown (it then also says that [chain]
/// moved to the top, so the caller skips its own message).
Future<bool> offerNotificationsAfterFirstFavorite(
  BuildContext context,
  WidgetRef ref,
  Chain chain,
) async {
  if (await _settledStatus(ref) != NotificationsStatus.off) return false;
  if (!context.mounted) return false;
  final favorites = ref.read(favoritesProvider).value ?? const <String>{};
  if (favorites.length != 1 || !favorites.contains(chain.id)) return false;
  final store = ref.read(notificationOfferStoreProvider);
  if (await store.wasOffered()) return false;
  if (!context.mounted) return false;
  await store.markOffered();
  if (!context.mounted) return false;

  final l10n = AppLocalizations.of(context);
  final accepted = await showNotificationOffer(
    context,
    names: chain.name,
    lead: l10n.favoriteAdded(chain.name),
  );
  if (accepted && context.mounted) await turnOnNotifications(context, ref);
  return true;
}

/// Shows the offer window. [names] is the phrase for "who will tell you"
/// ([chainNamesPhrase]); [lead] an optional first line saying what just
/// happened. Resolves to true when the user said yes. The phone's back
/// button means "not now"; a tap beside the window does nothing (a stray
/// tap must not answer the question).
Future<bool> showNotificationOffer(
  BuildContext context, {
  required String names,
  String? lead,
}) async {
  final l10n = AppLocalizations.of(context);
  final duration = context.motion(AppMotion.normal);
  final accepted = await showGeneralDialog<bool>(
    context: context,
    barrierDismissible: false,
    barrierLabel: l10n.notifyOfferNo,
    barrierColor: context.colors.scrim,
    transitionDuration: duration,
    pageBuilder: (context, _, _) =>
        NotificationOfferDialog(names: names, lead: lead),
    transitionBuilder: (context, animation, _, child) => FadeTransition(
      opacity: CurvedAnimation(parent: animation, curve: AppMotion.curve),
      child: child,
    ),
  );
  return accepted ?? false;
}

/// Switches notifications on (the phone may ask for permission first) and
/// says plainly how it went.
Future<void> turnOnNotifications(BuildContext context, WidgetRef ref) async {
  final l10n = AppLocalizations.of(context);
  unawaited(ref.read(notificationOfferStoreProvider).markOffered());
  try {
    await ref.read(notificationsProvider.notifier).turnOn();
  } on Object {
    if (context.mounted) showAppMessage(context, l10n.notifyFailed);
    return;
  }
  if (!context.mounted) return;
  showAppMessage(context, switch (notificationStatusOf(ref)) {
    NotificationsStatus.on => l10n.notifyTurnedOn,
    NotificationsStatus.off ||
    NotificationsStatus.blockedBySystem => l10n.notifyNotAllowed,
    NotificationsStatus.unavailable || null => l10n.notifyFailed,
  });
}

/// Switches notifications off. No "are you sure?": it is one tap to undo.
Future<void> turnOffNotifications(BuildContext context, WidgetRef ref) async {
  final l10n = AppLocalizations.of(context);
  unawaited(ref.read(notificationOfferStoreProvider).markOffered());
  try {
    await ref.read(notificationsProvider.notifier).turnOff();
  } on Object {
    if (context.mounted) showAppMessage(context, l10n.notifyFailed);
    return;
  }
  if (!context.mounted) return;
  final off = notificationStatusOf(ref) != NotificationsStatus.on;
  showAppMessage(context, off ? l10n.notifyTurnedOff : l10n.notifyFailed);
}

/// The offer window: a bell, the question, one plain sentence of what will
/// happen, what to press in the phone's own window, and two big answers.
class NotificationOfferDialog extends StatelessWidget {
  const NotificationOfferDialog({super.key, required this.names, this.lead});

  final String names;
  final String? lead;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    return SafeArea(
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpace.screen),
          child: ConstrainedBox(
            constraints: const BoxConstraints(
              maxWidth: AppSize.maxContentWidth,
            ),
            child: Semantics(
              scopesRoute: true,
              namesRoute: true,
              explicitChildNodes: true,
              label: l10n.notifyOfferTitle,
              child: Material(
                color: c.surface,
                shape: RoundedRectangleBorder(
                  borderRadius: AppRadius.lgAll,
                  side: BorderSide(color: c.line, width: AppSize.hairline),
                ),
                clipBehavior: Clip.antiAlias,
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(AppSpace.xl),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      if (lead != null) ...[
                        _LeadLine(text: lead!),
                        const SizedBox(height: AppSpace.lg),
                      ],
                      Align(
                        alignment: Alignment.centerLeft,
                        child: ExcludeSemantics(
                          child: Container(
                            width: AppSize.dialogArt,
                            height: AppSize.dialogArt,
                            decoration: BoxDecoration(
                              color: c.primarySoft,
                              shape: BoxShape.circle,
                            ),
                            child: Icon(
                              Icons.notifications_active_rounded,
                              size: AppSize.iconLarge,
                              color: c.onPrimarySoft,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: AppSpace.md),
                      Semantics(
                        header: true,
                        child: Text(
                          l10n.notifyOfferTitle,
                          style: AppType.section.copyWith(color: c.ink),
                        ),
                      ),
                      const SizedBox(height: AppSpace.sm),
                      Text(
                        l10n.notifyOfferMessage(names),
                        style: AppType.body.copyWith(color: c.ink),
                      ),
                      const SizedBox(height: AppSpace.md),
                      InfoNote(text: l10n.notifyOfferPermissionNote),
                      const SizedBox(height: AppSpace.xl),
                      AppButton(
                        key: const ValueKey('notify-offer-yes'),
                        label: l10n.notifyOfferYes,
                        icon: Icons.notifications_active_rounded,
                        expand: true,
                        onPressed: () => Navigator.of(context).pop(true),
                      ),
                      const SizedBox(height: AppSpace.sm),
                      AppButton(
                        key: const ValueKey('notify-offer-no'),
                        label: l10n.notifyOfferNo,
                        kind: AppButtonKind.outline,
                        expand: true,
                        onPressed: () => Navigator.of(context).pop(false),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// "Şok en üste alındı." with a gold star: what the tap that opened the
/// window just did (the card left the user's finger).
class _LeadLine extends StatelessWidget {
  const _LeadLine({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Same drawing as a starred FavoriteStar: fill plus dark outline.
        ExcludeSemantics(
          child: Stack(
            children: [
              Icon(Icons.star_rounded, size: AppSize.icon, color: c.star),
              Icon(
                Icons.star_outline_rounded,
                size: AppSize.icon,
                color: c.starOutline,
              ),
            ],
          ),
        ),
        const SizedBox(width: AppSpace.xs),
        Expanded(
          child: Text(text, style: AppType.bodyStrong.copyWith(color: c.ink)),
        ),
      ],
    );
  }
}
