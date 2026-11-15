import 'package:flutter/material.dart';

import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../../design/typography.dart';
import '../../design/widgets/app_buttons.dart';
import '../../l10n/app_localizations.dart';
import 'zoomable_page.dart';

/// The viewer's bottom bar. Always visible, never laid over the page:
///
///     ‹   3 / 8   ›        −  +
///
/// Arrows are the primary action (filled, 64 dp); zoom buttons are quieter
/// (56 dp) and set apart so the two pairs are not confused. A button that
/// cannot act right now fades but keeps its place.
class ViewerControls extends StatelessWidget {
  const ViewerControls({
    super.key,
    required this.page,
    required this.pageCount,
    required this.zoom,
    required this.onPrevious,
    required this.onNext,
    required this.onZoomIn,
    required this.onZoomOut,
    this.onPickPage,
  });

  /// 0-based index of the page on screen.
  final int page;
  final int pageCount;
  final ZoomStatus zoom;
  final VoidCallback onPrevious;
  final VoidCallback onNext;
  final VoidCallback onZoomIn;
  final VoidCallback onZoomOut;

  /// Opens the page picker. When set, the indicator is drawn as a button
  /// (long catalogs); when null it is plain text (short brochures).
  final VoidCallback? onPickPage;

  /// Narrower than this, the indicator would become too small next to four
  /// buttons; the zoom pair then moves to its own row.
  static const double _minIndicatorWidth = 64;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);

    final previous = AppIconButton(
      key: const ValueKey('viewer-previous'),
      icon: Icons.chevron_left_rounded,
      label: l10n.pagePrevious,
      kind: AppButtonKind.primary,
      size: AppSize.touchLarge,
      iconSize: AppSize.iconLarge + AppSpace.xs,
      onPressed: page > 0 ? onPrevious : null,
    );
    final next = AppIconButton(
      key: const ValueKey('viewer-next'),
      icon: Icons.chevron_right_rounded,
      label: l10n.pageNext,
      kind: AppButtonKind.primary,
      size: AppSize.touchLarge,
      iconSize: AppSize.iconLarge + AppSpace.xs,
      onPressed: page < pageCount - 1 ? onNext : null,
    );
    final zoomOut = AppIconButton(
      key: const ValueKey('viewer-zoom-out'),
      icon: Icons.remove_rounded,
      label: l10n.zoomOut,
      iconSize: AppSize.iconLarge,
      onPressed: zoom.canZoomOut ? onZoomOut : null,
    );
    final zoomIn = AppIconButton(
      key: const ValueKey('viewer-zoom-in'),
      icon: Icons.add_rounded,
      label: l10n.zoomIn,
      iconSize: AppSize.iconLarge,
      onPressed: zoom.canZoomIn ? onZoomIn : null,
    );
    final indicatorText = Text(
      l10n.pageIndicator(page + 1, pageCount),
      key: const ValueKey('viewer-indicator'),
      maxLines: 1,
      style: AppType.pageIndicator.copyWith(color: c.ink),
    );
    final pickPage = onPickPage;
    final Widget indicator = pickPage == null
        ? Semantics(
            label: l10n.pageIndicatorSpoken(page + 1, pageCount),
            excludeSemantics: true,
            liveRegion: true,
            child: FittedBox(fit: BoxFit.scaleDown, child: indicatorText),
          )
        : Semantics(
            button: true,
            label: l10n.pagePickerOpenSpoken(page + 1, pageCount),
            excludeSemantics: true,
            liveRegion: true,
            child: Material(
              key: const ValueKey('viewer-pick-page'),
              color: c.surface,
              shape: RoundedRectangleBorder(
                borderRadius: AppRadius.mdAll,
                side: BorderSide(color: c.lineStrong, width: AppSize.outline),
              ),
              clipBehavior: Clip.antiAlias,
              child: InkWell(
                onTap: pickPage,
                child: ConstrainedBox(
                  constraints: const BoxConstraints(
                    minHeight: AppSize.touch,
                    minWidth: AppSize.touch,
                  ),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpace.xs,
                    ),
                    // No icon beside the number: it would squeeze the
                    // digits. The outlined shape is this app's sign for
                    // "press me" (like "Geri").
                    child: FittedBox(
                      fit: BoxFit.scaleDown,
                      child: indicatorText,
                    ),
                  ),
                ),
              ),
            ),
          );

    const fixedWidth =
        AppSize.touchLarge * 2 +
        AppSize.touch * 2 +
        AppSpace.xs * 3 +
        AppSpace.md;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: c.paper,
        border: Border(
          top: BorderSide(color: c.line, width: AppSize.hairline),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpace.sm,
          vertical: AppSpace.sm,
        ),
        child: LayoutBuilder(
          builder: (context, constraints) {
            final pager = Row(
              children: [
                previous,
                const SizedBox(width: AppSpace.xs),
                Expanded(child: Center(child: indicator)),
                const SizedBox(width: AppSpace.xs),
                next,
              ],
            );
            final zoomPair = Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                zoomOut,
                const SizedBox(width: AppSpace.xs),
                zoomIn,
              ],
            );
            if (constraints.maxWidth - fixedWidth < _minIndicatorWidth) {
              return Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  pager,
                  const SizedBox(height: AppSpace.xs),
                  zoomPair,
                ],
              );
            }
            return Row(
              children: [
                Expanded(child: pager),
                const SizedBox(width: AppSpace.md),
                zoomPair,
              ],
            );
          },
        ),
      ),
    );
  }
}
