/// Buttons. Every one is at least 56 dp tall and wide, has a visible shape
/// (never text alone) and grows with its label instead of cutting it.
library;

import 'package:flutter/material.dart';

import '../theme.dart';
import '../tokens.dart';
import '../typography.dart';

enum AppButtonKind {
  /// The one main action of a screen.
  primary,

  /// A quieter action next to (or instead of) a primary one.
  tonal,

  /// The least prominent action; still a clearly outlined button.
  outline,
}

({Color background, Color foreground, Color border}) _buttonColors(
  AppColors c,
  AppButtonKind kind,
) => switch (kind) {
  AppButtonKind.primary => (
    background: c.primary,
    foreground: c.onPrimary,
    border: c.primary,
  ),
  AppButtonKind.tonal => (
    background: c.primarySoft,
    foreground: c.onPrimarySoft,
    border: c.primarySoft,
  ),
  AppButtonKind.outline => (
    background: c.surface,
    foreground: c.ink,
    border: c.lineStrong,
  ),
};

/// Opacity of a button that cannot be pressed right now. It keeps its place
/// so the layout never jumps.
const double _disabledOpacity = 0.38;

/// A labelled button, optionally with a leading icon.
class AppButton extends StatelessWidget {
  const AppButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.kind = AppButtonKind.primary,
    this.expand = false,
    this.minHeight = AppSize.touchLarge,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final AppButtonKind kind;

  /// Fill the available width.
  final bool expand;

  final double minHeight;

  @override
  Widget build(BuildContext context) {
    final colors = _buttonColors(context.colors, kind);
    final enabled = onPressed != null;
    return Opacity(
      opacity: enabled ? 1 : _disabledOpacity,
      child: Material(
        color: colors.background,
        shape: RoundedRectangleBorder(
          borderRadius: AppRadius.mdAll,
          side: BorderSide(color: colors.border, width: AppSize.outline),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onPressed,
          child: ConstrainedBox(
            constraints: BoxConstraints(
              minHeight: minHeight,
              minWidth: AppSize.touch,
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpace.lg,
                vertical: AppSpace.sm,
              ),
              child: Row(
                mainAxisSize: expand ? MainAxisSize.max : MainAxisSize.min,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (icon != null) ...[
                    Icon(icon, size: AppSize.icon, color: colors.foreground),
                    const SizedBox(width: AppSpace.sm),
                  ],
                  Flexible(
                    child: Text(
                      label,
                      textAlign: TextAlign.center,
                      style: AppType.label.copyWith(color: colors.foreground),
                    ),
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

/// A square icon-only button (arrows, + / −, star). [label] is what a screen
/// reader says and what a long press shows.
class AppIconButton extends StatelessWidget {
  const AppIconButton({
    super.key,
    required this.icon,
    required this.label,
    required this.onPressed,
    this.kind = AppButtonKind.tonal,
    this.size = AppSize.touch,
    this.iconSize = AppSize.icon,
    this.iconColor,
  });

  final IconData icon;
  final String label;
  final VoidCallback? onPressed;
  final AppButtonKind kind;
  final double size;
  final double iconSize;

  /// Overrides the kind's icon colour (the favourite star).
  final Color? iconColor;

  @override
  Widget build(BuildContext context) {
    final colors = _buttonColors(context.colors, kind);
    final enabled = onPressed != null;
    return Semantics(
      button: true,
      enabled: enabled,
      label: label,
      excludeSemantics: true,
      child: Tooltip(
        message: label,
        child: Opacity(
          opacity: enabled ? 1 : _disabledOpacity,
          child: Material(
            color: colors.background,
            shape: RoundedRectangleBorder(
              borderRadius: AppRadius.mdAll,
              side: BorderSide(color: colors.border, width: AppSize.outline),
            ),
            clipBehavior: Clip.antiAlias,
            child: InkWell(
              onTap: onPressed,
              child: SizedBox(
                width: size,
                height: size,
                child: Icon(
                  icon,
                  size: iconSize,
                  color: iconColor ?? colors.foreground,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// The favourite star. Filled gold with a dark outline when on, an outline
/// when off: the shape changes, not only the colour.
class FavoriteStar extends StatelessWidget {
  const FavoriteStar({
    super.key,
    required this.isFavorite,
    required this.label,
    required this.onPressed,
    this.onPlate = false,
  });

  final bool isFavorite;

  /// Screen-reader text, e.g. "BİM: sık baktıklarıma ekle".
  final String label;
  final VoidCallback? onPressed;

  /// Draw a small plate behind the star (used on top of logo plates, whose
  /// colour is unknown).
  final bool onPlate;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final star = Stack(
      alignment: Alignment.center,
      children: [
        if (isFavorite)
          Icon(Icons.star_rounded, size: AppSize.iconLarge, color: c.star),
        Icon(
          Icons.star_outline_rounded,
          size: AppSize.iconLarge,
          color: isFavorite ? c.starOutline : c.inkSoft,
        ),
      ],
    );
    return Semantics(
      button: true,
      toggled: isFavorite,
      label: label,
      excludeSemantics: true,
      child: Tooltip(
        message: label,
        child: Material(
          color: onPlate ? c.surface : Colors.transparent,
          shape: RoundedRectangleBorder(
            borderRadius: AppRadius.mdAll,
            side: onPlate
                ? BorderSide(color: c.line, width: AppSize.hairline)
                : BorderSide.none,
          ),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: onPressed,
            child: SizedBox.square(dimension: AppSize.touch, child: star),
          ),
        ),
      ),
    );
  }
}
