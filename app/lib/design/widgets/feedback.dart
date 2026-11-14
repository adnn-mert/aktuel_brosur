/// Small informational pieces: notice strips, full-screen state views,
/// section headings, pills and loading skeletons.
library;

import 'package:flutter/material.dart';

import '../theme.dart';
import '../tokens.dart';
import '../typography.dart';
import 'app_buttons.dart';

/// A calm strip that tells the user about a condition (offline, outdated
/// data, update needed). It informs; it never alarms.
class NoticeStrip extends StatelessWidget {
  const NoticeStrip({
    super.key,
    required this.icon,
    required this.text,
    this.detail,
  });

  final IconData icon;
  final String text;

  /// Optional second, quieter sentence.
  final String? detail;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Semantics(
      container: true,
      liveRegion: true,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: c.notice,
          borderRadius: AppRadius.mdAll,
          border: Border.all(color: c.noticeLine, width: AppSize.hairline),
        ),
        child: Padding(
          padding: const EdgeInsets.all(AppSpace.md),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ExcludeSemantics(
                child: Icon(icon, size: AppSize.icon, color: c.onNotice),
              ),
              const SizedBox(width: AppSpace.sm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      text,
                      style: AppType.bodyStrong.copyWith(color: c.onNotice),
                    ),
                    if (detail != null) ...[
                      const SizedBox(height: AppSpace.xxs),
                      Text(
                        detail!,
                        style: AppType.body.copyWith(color: c.onNotice),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// A whole-area message: what happened, what to do, one big button.
/// Used for "no internet", "nothing here", "could not open".
class StateView extends StatelessWidget {
  const StateView({
    super.key,
    required this.title,
    this.message,
    this.icon,
    this.art,
    this.actionLabel,
    this.actionIcon,
    this.onAction,
    this.secondaryLabel,
    this.secondaryIcon,
    this.onSecondary,
  });

  final String title;
  final String? message;

  /// Shown in a soft disc above the title, unless [art] is given.
  final IconData? icon;

  /// Custom illustration (e.g. the logo) instead of [icon].
  final Widget? art;

  final String? actionLabel;
  final IconData? actionIcon;
  final VoidCallback? onAction;

  final String? secondaryLabel;
  final IconData? secondaryIcon;
  final VoidCallback? onSecondary;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final illustration =
        art ??
        (icon == null
            ? null
            : Container(
                width: AppSize.stateArt,
                height: AppSize.stateArt,
                decoration: BoxDecoration(
                  color: c.primarySoft,
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  icon,
                  size: AppSize.stateArt / 2,
                  color: c.onPrimarySoft,
                ),
              ));
    return LayoutBuilder(
      builder: (context, constraints) => SingleChildScrollView(
        child: ConstrainedBox(
          constraints: BoxConstraints(minHeight: constraints.maxHeight),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(
                maxWidth: AppSize.maxContentWidth,
              ),
              child: Padding(
                padding: const EdgeInsets.all(AppSpace.xl),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (illustration != null) ...[
                      ExcludeSemantics(child: illustration),
                      const SizedBox(height: AppSpace.xl),
                    ],
                    Semantics(
                      header: true,
                      child: Text(
                        title,
                        textAlign: TextAlign.center,
                        style: AppType.headline.copyWith(color: c.ink),
                      ),
                    ),
                    if (message != null) ...[
                      const SizedBox(height: AppSpace.sm),
                      Text(
                        message!,
                        textAlign: TextAlign.center,
                        style: AppType.body.copyWith(color: c.inkSoft),
                      ),
                    ],
                    if (actionLabel != null) ...[
                      const SizedBox(height: AppSpace.xl),
                      AppButton(
                        label: actionLabel!,
                        icon: actionIcon,
                        onPressed: onAction,
                        expand: true,
                      ),
                    ],
                    if (secondaryLabel != null) ...[
                      const SizedBox(height: AppSpace.sm),
                      AppButton(
                        label: secondaryLabel!,
                        icon: secondaryIcon,
                        onPressed: onSecondary,
                        kind: AppButtonKind.outline,
                        expand: true,
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Heading of a list section ("Bu hafta").
class SectionHeader extends StatelessWidget {
  const SectionHeader({super.key, required this.title, this.icon});

  final String title;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Semantics(
      header: true,
      child: Padding(
        padding: const EdgeInsets.only(top: AppSpace.xl, bottom: AppSpace.sm),
        child: Row(
          children: [
            if (icon != null) ...[
              ExcludeSemantics(
                child: Icon(icon, size: AppSize.icon, color: c.ink),
              ),
              const SizedBox(width: AppSpace.xs),
            ],
            Expanded(
              child: Text(title, style: AppType.section.copyWith(color: c.ink)),
            ),
          ],
        ),
      ),
    );
  }
}

/// A small filled label: "Yeni", "%20 indirim".
class Pill extends StatelessWidget {
  const Pill({super.key, required this.text, this.background, this.foreground});

  final String text;

  /// Default: the "fresh" red.
  final Color? background;
  final Color? foreground;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: background ?? c.fresh,
        borderRadius: AppRadius.pillAll,
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpace.sm,
          vertical: AppSpace.xxs,
        ),
        child: Text(
          text,
          style: AppType.badge.copyWith(color: foreground ?? c.onFresh),
        ),
      ),
    );
  }
}

/// A quiet placeholder block that breathes while content loads. Still when
/// motion is reduced.
class SkeletonBox extends StatefulWidget {
  const SkeletonBox({
    super.key,
    this.width,
    this.height,
    this.radius = AppRadius.lgAll,
  });

  final double? width;
  final double? height;
  final BorderRadius radius;

  @override
  State<SkeletonBox> createState() => _SkeletonBoxState();
}

class _SkeletonBoxState extends State<SkeletonBox>
    with SingleTickerProviderStateMixin {
  static const Duration _period = Duration(milliseconds: 1100);
  static const double _dim = 0.55;

  late final AnimationController _pulse = AnimationController(
    vsync: this,
    duration: _period,
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (context.reduceMotion) {
      _pulse.stop();
      _pulse.value = 0;
    } else if (!_pulse.isAnimating) {
      _pulse.repeat(reverse: true);
    }
  }

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return ExcludeSemantics(
      child: FadeTransition(
        opacity: Tween<double>(begin: 1, end: _dim).animate(_pulse),
        child: Container(
          width: widget.width,
          height: widget.height,
          decoration: BoxDecoration(
            color: c.surfaceSunken,
            borderRadius: widget.radius,
          ),
        ),
      ),
    );
  }
}

/// The standard card surface: rounded, soft shadow in light theme, hairline
/// edge in dark theme. Pass [onTap] to make the whole card a button.
class AppCard extends StatelessWidget {
  const AppCard({
    super.key,
    required this.child,
    this.onTap,
    this.padding = const EdgeInsets.all(AppSpace.sm),
    this.semanticLabel,
  });

  final Widget child;
  final VoidCallback? onTap;
  final EdgeInsets padding;

  /// When set, the card is announced as one button with this label and its
  /// children are not read separately.
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final card = DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: AppRadius.lgAll,
        boxShadow: AppShadows.card(c),
      ),
      child: Material(
        color: c.surface,
        shape: RoundedRectangleBorder(
          borderRadius: AppRadius.lgAll,
          side: BorderSide(color: c.line, width: AppSize.hairline),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Padding(padding: padding, child: child),
        ),
      ),
    );
    if (semanticLabel == null) return card;
    return Semantics(
      button: onTap != null,
      label: semanticLabel,
      excludeSemantics: true,
      child: card,
    );
  }
}

/// Shows a snack message, replacing any that is still on screen. It stays
/// long enough to be read slowly.
void showAppMessage(BuildContext context, String text) {
  ScaffoldMessenger.of(context)
    ..clearSnackBars()
    ..showSnackBar(SnackBar(content: Text(text), duration: AppMotion.snack));
}
