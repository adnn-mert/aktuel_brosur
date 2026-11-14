/// Screen frame and the top bar with the always-visible "Geri" button.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../l10n/app_localizations.dart';
import '../theme.dart';
import '../tokens.dart';
import '../typography.dart';

/// Above this system font scale, bars stack their parts vertically instead
/// of squeezing them side by side.
const double stackedLayoutTextScale = 1.3;

extension TextScaleContext on BuildContext {
  /// The effective font scale (1.0 = system default).
  double get textScale => MediaQuery.textScalerOf(this).scale(1);

  /// True when text is large enough that side-by-side bars should stack.
  bool get useStackedBars => textScale > stackedLayoutTextScale;
}

/// Frame of every screen: paper background, safe areas, optional top bar and
/// bottom bar that never scroll away.
class AppScaffold extends StatelessWidget {
  const AppScaffold({
    super.key,
    required this.body,
    this.topBar,
    this.bottomBar,
    this.background,
  });

  final Widget body;
  final Widget? topBar;
  final Widget? bottomBar;

  /// Defaults to the paper colour.
  final Color? background;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: overlayStyleFor(c),
      child: Scaffold(
        backgroundColor: c.paper,
        body: SafeArea(
          bottom: false,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              ?topBar,
              Expanded(
                child: ColoredBox(
                  color: background ?? c.paper,
                  child: bottomBar == null
                      ? SafeArea(top: false, child: body)
                      : body,
                ),
              ),
              if (bottomBar != null) SafeArea(top: false, child: bottomBar!),
            ],
          ),
        ),
      ),
    );
  }
}

/// Top bar: a big "Geri" button, a title and an optional trailing control.
///
/// With a large system font the title moves to its own row so nothing is
/// squeezed or cut.
class AppTopBar extends StatelessWidget {
  const AppTopBar({
    super.key,
    this.title,
    this.subtitle,
    this.titleWidget,
    this.trailing,
    this.onBack,
    this.keepOnOneRow = false,
  }) : assert(title == null || titleWidget == null);

  final String? title;
  final String? subtitle;

  /// Shown instead of [title] (e.g. a market logo).
  final Widget? titleWidget;

  final Widget? trailing;

  /// Defaults to leaving the screen.
  final VoidCallback? onBack;

  /// Keep the title beside "Geri" even with a very large font, shrinking it
  /// to fit instead of moving it to its own row. For screens whose content
  /// needs every bit of height (the brochure viewer, the web view), where
  /// the title only confirms what the user just chose.
  final bool keepOnOneRow;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);

    final back = BackButtonPill(
      label: l10n.back,
      onPressed: onBack ?? () => Navigator.of(context).maybePop(),
    );

    Widget? heading;
    if (titleWidget != null) {
      heading = titleWidget;
    } else if (title != null) {
      heading = Semantics(
        header: true,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _fitted(Text(title!, style: AppType.title.copyWith(color: c.ink))),
            if (subtitle != null && subtitle!.isNotEmpty)
              _fitted(
                Text(subtitle!, style: AppType.body.copyWith(color: c.inkSoft)),
              ),
          ],
        ),
      );
    }

    final Widget content;
    if (context.useStackedBars && !keepOnOneRow) {
      content = Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(children: [back, const Spacer(), ?trailing]),
          if (heading != null) ...[
            const SizedBox(height: AppSpace.xs),
            Align(alignment: Alignment.centerLeft, child: heading),
          ],
        ],
      );
    } else {
      content = Row(
        children: [
          back,
          const SizedBox(width: AppSpace.md),
          Expanded(
            child: Align(
              alignment: Alignment.centerLeft,
              child: heading ?? const SizedBox.shrink(),
            ),
          ),
          if (trailing != null) ...[
            const SizedBox(width: AppSpace.xs),
            trailing!,
          ],
        ],
      );
    }

    return DecoratedBox(
      decoration: BoxDecoration(
        color: c.paper,
        border: Border(
          bottom: BorderSide(color: c.line, width: AppSize.hairline),
        ),
      ),
      child: ConstrainedBox(
        constraints: const BoxConstraints(minHeight: AppSize.topBar),
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpace.sm,
            vertical: AppSpace.xs,
          ),
          child: content,
        ),
      ),
    );
  }

  Widget _fitted(Text text) => keepOnOneRow
      ? FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.centerLeft,
          child: text,
        )
      : text;
}

/// "‹ Geri": icon and word together, so it is never mistaken or missed.
class BackButtonPill extends StatelessWidget {
  const BackButtonPill({
    super.key,
    required this.label,
    required this.onPressed,
  });

  final String label;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Semantics(
      button: true,
      label: label,
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
            constraints: const BoxConstraints(
              minHeight: AppSize.touch,
              minWidth: AppSize.touch,
            ),
            child: Padding(
              padding: const EdgeInsets.only(
                left: AppSpace.xs,
                right: AppSpace.md,
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.chevron_left_rounded,
                    size: AppSize.iconLarge,
                    color: c.ink,
                  ),
                  Text(label, style: AppType.label.copyWith(color: c.ink)),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Centres content and keeps it from stretching across a tablet.
class ContentWidth extends StatelessWidget {
  const ContentWidth({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) => Align(
    alignment: Alignment.topCenter,
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: AppSize.maxContentWidth),
      child: child,
    ),
  );
}
