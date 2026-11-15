import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/data.dart';
import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../../design/typography.dart';
import '../../design/widgets/app_buttons.dart';
import '../../design/widgets/app_scaffold.dart';
import '../../design/widgets/feedback.dart';
import '../../l10n/app_localizations.dart';
import 'notification_offer.dart';
import 'notification_offer_store.dart';

/// The always-findable switch for "tell me when my favourite markets publish
/// a new brochure". It sits on the home screen right under the favourite
/// markets it is about; the home screen has no menu, so there is no settings
/// screen to hide it in.
///
/// * unknown / [NotificationsStatus.unavailable]: nothing at all (not even
///   spacing), the home screen looks exactly as without the feature;
/// * [NotificationsStatus.off]: one outlined row-button that opens the offer
///   window;
/// * [NotificationsStatus.on]: a green panel that says it is on, for which
///   markets, and a "Bildirimi kapat" button;
/// * [NotificationsStatus.blockedBySystem]: a quiet panel that says the phone
///   does not allow it, with the steps behind a "Nasıl açılır?" button.
class NotificationControl extends ConsumerStatefulWidget {
  const NotificationControl({super.key, required this.chainNames});

  /// Favourite market names in home-screen order. With none, nothing shows.
  final List<String> chainNames;

  @override
  ConsumerState<NotificationControl> createState() =>
      _NotificationControlState();
}

class _NotificationControlState extends ConsumerState<NotificationControl> {
  bool _busy = false;
  bool _showSteps = false;

  Future<void> _run(Future<void> Function() action) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await action();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _offer() => _run(() async {
    final l10n = AppLocalizations.of(context);
    await ref.read(notificationOfferStoreProvider).markOffered();
    if (!mounted) return;
    final accepted = await showNotificationOffer(
      context,
      names: chainNamesPhrase(l10n, widget.chainNames),
    );
    if (accepted && mounted) await turnOnNotifications(context, ref);
  });

  Future<void> _turnOff() => _run(() => turnOffNotifications(context, ref));

  /// Opens the phone's notification page for this app. When that is not
  /// possible the written steps open instead (and stay open), with a message
  /// saying so. Coming back after allowing turns the panel into "on" by
  /// itself (the data layer re-checks on resume).
  Future<void> _openSettings() => _run(() async {
    final l10n = AppLocalizations.of(context);
    final opened = await ref
        .read(notificationsProvider.notifier)
        .openSystemSettings();
    if (!mounted || opened) return;
    setState(() => _showSteps = true);
    showAppMessage(context, l10n.notifySettingsFailed);
  });

  @override
  Widget build(BuildContext context) {
    final status = ref.watch(notificationsProvider).value?.status;
    final Widget? content = switch (status) {
      null || NotificationsStatus.unavailable => null,
      NotificationsStatus.off => _OffEntry(onPressed: _busy ? null : _offer),
      NotificationsStatus.on => _OnPanel(
        names: widget.chainNames,
        onTurnOff: _busy ? null : _turnOff,
      ),
      NotificationsStatus.blockedBySystem => _BlockedPanel(
        showSteps: _showSteps,
        onOpenSettings: _busy ? null : _openSettings,
        onToggleSteps: () => setState(() => _showSteps = !_showSteps),
      ),
    };
    if (content == null || widget.chainNames.isEmpty) {
      return const SizedBox.shrink();
    }
    return Padding(
      padding: const EdgeInsets.only(top: AppSpace.lg),
      child: content,
    );
  }
}

/// Off: "🔔 Yeni broşür çıkınca haber ver / Bildirim şu an kapalı ›". The
/// app's "this can be pressed" look (cream, dark outline), like the search
/// button; the bell square is the quiet green, not the filled action green,
/// because this is an offer, not the screen's main job.
class _OffEntry extends StatelessWidget {
  const _OffEntry({required this.onPressed});

  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    return Semantics(
      key: const ValueKey('notify-off'),
      button: true,
      enabled: onPressed != null,
      label: l10n.notifyOffSpoken,
      excludeSemantics: true,
      child: Material(
        color: c.surface,
        shape: RoundedRectangleBorder(
          borderRadius: AppRadius.mdAll,
          side: BorderSide(color: c.lineStrong, width: AppSize.outline),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onPressed,
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: AppSize.touchLarge),
            child: Padding(
              padding: const EdgeInsets.all(AppSpace.sm),
              child: Row(
                children: [
                  Expanded(
                    child: _IconAndWords(
                      icon: _IconSquare(
                        icon: Icons.notifications_none_rounded,
                        background: c.primarySoft,
                        foreground: c.onPrimarySoft,
                      ),
                      title: Text(
                        l10n.notifyOffTitle,
                        style: AppType.label.copyWith(color: c.ink),
                      ),
                      detail: Text(
                        l10n.notifyOffDetail,
                        style: AppType.body.copyWith(color: c.inkSoft),
                      ),
                    ),
                  ),
                  // With a very large font the words need the whole width.
                  if (!context.useStackedBars)
                    Icon(
                      Icons.chevron_right_rounded,
                      size: AppSize.iconLarge,
                      color: c.ink,
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// On: a green panel (the quiet action tint, not an alarm) that confirms in
/// words, names the markets, and offers the way back in a visible button.
class _OnPanel extends StatelessWidget {
  const _OnPanel({required this.names, required this.onTurnOff});

  final List<String> names;
  final VoidCallback? onTurnOff;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    return _Panel(
      key: const ValueKey('notify-on'),
      background: c.primarySoft,
      border: c.primarySoft,
      icon: Icons.notifications_active_rounded,
      iconBackground: c.primary,
      iconForeground: c.onPrimary,
      title: l10n.notifyOnTitle,
      titleColor: c.onPrimarySoft,
      detail: l10n.notifyOnDetail(chainNamesPhrase(l10n, names)),
      detailColor: c.onPrimarySoft,
      children: [
        AppButton(
          key: const ValueKey('notify-turn-off'),
          label: l10n.notifyTurnOff,
          icon: Icons.notifications_off_outlined,
          kind: AppButtonKind.outline,
          minHeight: AppSize.touch,
          onPressed: onTurnOff,
        ),
      ],
    );
  }
}

/// Blocked by the phone: calm, not yellow. The user may have said no on
/// purpose; this must not read like a warning that waits to be fixed.
///
/// One big button opens the phone's own page for this app's notifications
/// (the shortest way: a single switch to flip there). The written steps stay
/// one quieter button away, and open by themselves when the phone's page
/// cannot be opened.
class _BlockedPanel extends StatelessWidget {
  const _BlockedPanel({
    required this.showSteps,
    required this.onOpenSettings,
    required this.onToggleSteps,
  });

  final bool showSteps;
  final VoidCallback? onOpenSettings;
  final VoidCallback onToggleSteps;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    // With a very large font an icon beside the words broke "ayarlarını"
    // in two on a 320 dp phone; the words get the whole button instead.
    final withIcons = !context.useStackedBars;
    final steps = [
      l10n.notifyBlockedStep1,
      l10n.notifyBlockedStep2(l10n.appTitle),
      l10n.notifyBlockedStep3,
    ];
    return _Panel(
      key: const ValueKey('notify-blocked'),
      background: c.surface,
      border: c.line,
      icon: Icons.notifications_off_rounded,
      iconBackground: c.surfaceSunken,
      iconForeground: c.ink,
      title: l10n.notifyBlockedTitle,
      titleColor: c.ink,
      detail: l10n.notifyBlockedDetail,
      detailColor: c.inkSoft,
      children: [
        AppButton(
          key: const ValueKey('notify-open-settings'),
          label: l10n.notifyOpenSettings,
          icon: withIcons ? Icons.settings_rounded : null,
          kind: AppButtonKind.tonal,
          expand: true,
          onPressed: onOpenSettings,
        ),
        const SizedBox(height: AppSpace.sm),
        AnimatedSize(
          duration: context.motion(AppMotion.normal),
          curve: AppMotion.curve,
          alignment: Alignment.topCenter,
          child: showSteps
              ? Padding(
                  padding: const EdgeInsets.only(bottom: AppSpace.md),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      for (var i = 0; i < steps.length; i++) ...[
                        if (i > 0) const SizedBox(height: AppSpace.sm),
                        _Step(number: i + 1, text: steps[i]),
                      ],
                    ],
                  ),
                )
              : const SizedBox(width: double.infinity),
        ),
        AppButton(
          key: const ValueKey('notify-how-to'),
          label: showSteps
              ? l10n.notifyBlockedHideSteps
              : l10n.notifyBlockedHowTo,
          icon: !withIcons
              ? null
              : showSteps
              ? Icons.expand_less_rounded
              : Icons.help_outline_rounded,
          kind: AppButtonKind.outline,
          minHeight: AppSize.touch,
          onPressed: onToggleSteps,
        ),
      ],
    );
  }
}

/// One numbered step of the phone-settings instructions.
class _Step extends StatelessWidget {
  const _Step({required this.number, required this.text});

  final int number;
  final String text;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Semantics(
      container: true,
      label: l10n.notifyStepSpoken(number, text),
      excludeSemantics: true,
      child: _numbered(context, number: number, text: text),
    );
  }

  /// Number square beside the sentence; with a very large font it sits above
  /// it, so the sentence keeps the whole width (beside it, "uygulamasını"
  /// broke mid-word on a 320 dp phone).
  Widget _numbered(
    BuildContext context, {
    required int number,
    required String text,
  }) {
    final c = context.colors;
    final square = Container(
      constraints: const BoxConstraints(
        minWidth: AppSize.stepNumber,
        minHeight: AppSize.stepNumber,
      ),
      decoration: BoxDecoration(
        color: c.primarySoft,
        borderRadius: AppRadius.smAll,
      ),
      // Sized by its digit (at least the square), never stretched.
      child: Center(
        widthFactor: 1,
        heightFactor: 1,
        child: Text(
          '$number',
          style: AppType.bodyStrong.copyWith(color: c.onPrimarySoft),
        ),
      ),
    );
    final sentence = Text(text, style: AppType.body.copyWith(color: c.ink));
    if (context.useStackedBars) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          square,
          const SizedBox(height: AppSpace.xxs),
          sentence,
        ],
      );
    }
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        square,
        const SizedBox(width: AppSpace.sm),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.only(top: AppSpace.xxs),
            child: sentence,
          ),
        ),
      ],
    );
  }
}

/// Shared frame of the "on" and "blocked" panels: icon square, title,
/// sentence, then the panel's own controls underneath (never beside: with a
/// large font a side-by-side button would squeeze the words).
class _Panel extends StatelessWidget {
  const _Panel({
    super.key,
    required this.background,
    required this.border,
    required this.icon,
    required this.iconBackground,
    required this.iconForeground,
    required this.title,
    required this.titleColor,
    required this.detail,
    required this.detailColor,
    required this.children,
  });

  final Color background;
  final Color border;
  final IconData icon;
  final Color iconBackground;
  final Color iconForeground;
  final String title;
  final Color titleColor;
  final String detail;
  final Color detailColor;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: background,
        borderRadius: AppRadius.mdAll,
        border: Border.all(color: border, width: AppSize.hairline),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Semantics(
              container: true,
              child: _IconAndWords(
                iconOnTop: true,
                icon: _IconSquare(
                  icon: icon,
                  background: iconBackground,
                  foreground: iconForeground,
                ),
                title: Semantics(
                  header: true,
                  child: Text(
                    title,
                    style: AppType.label.copyWith(color: titleColor),
                  ),
                ),
                detail: Text(
                  detail,
                  style: AppType.body.copyWith(color: detailColor),
                ),
              ),
            ),
            const SizedBox(height: AppSpace.md),
            ...children,
          ],
        ),
      ),
    );
  }
}

/// Icon square beside a bold line and a sentence; with a very large font the
/// icon moves above the words, which then get the whole width (beside the
/// icon, a 320 dp phone at font scale 2.0 broke "Bildirimler" mid-word).
class _IconAndWords extends StatelessWidget {
  const _IconAndWords({
    required this.icon,
    required this.title,
    required this.detail,
    this.iconOnTop = false,
  });

  final Widget icon;
  final Widget title;
  final Widget detail;

  /// Panels (several lines of text) keep the icon at the top of the words;
  /// the button centres it, like the "Ürün ara" button.
  final bool iconOnTop;

  @override
  Widget build(BuildContext context) {
    final words = Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        title,
        const SizedBox(height: AppSpace.xxs),
        detail,
      ],
    );
    if (context.useStackedBars) {
      return Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          icon,
          const SizedBox(height: AppSpace.sm),
          words,
        ],
      );
    }
    return Row(
      crossAxisAlignment: iconOnTop
          ? CrossAxisAlignment.start
          : CrossAxisAlignment.center,
      children: [
        icon,
        const SizedBox(width: AppSpace.sm),
        Expanded(child: words),
      ],
    );
  }
}

class _IconSquare extends StatelessWidget {
  const _IconSquare({
    required this.icon,
    required this.background,
    required this.foreground,
  });

  final IconData icon;
  final Color background;
  final Color foreground;

  @override
  Widget build(BuildContext context) => ExcludeSemantics(
    child: Container(
      width: AppSize.entryIcon,
      height: AppSize.entryIcon,
      decoration: BoxDecoration(
        color: background,
        borderRadius: AppRadius.smAll,
      ),
      child: Icon(icon, size: AppSize.icon, color: foreground),
    ),
  );
}
