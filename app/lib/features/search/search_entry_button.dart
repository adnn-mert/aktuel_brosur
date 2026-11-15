import 'package:flutter/material.dart';

import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../../design/typography.dart';
import '../../design/widgets/app_scaffold.dart';
import '../../l10n/app_localizations.dart';

/// The home screen's way into the product search: one wide, tall button that
/// says what it does in words ("Ürün ara") and why ("Hangi markette kaç
/// lira?"). Never a lone magnifier icon in a corner.
///
/// It wears the app's "this can be pressed" look (cream surface, dark
/// outline) rather than the filled action colour: choosing a market stays
/// the main job of the home screen.
class SearchEntryButton extends StatelessWidget {
  const SearchEntryButton({super.key, required this.onPressed});

  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    return Semantics(
      button: true,
      label: l10n.searchEntrySpoken,
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
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpace.sm,
                vertical: AppSpace.sm,
              ),
              child: Row(
                children: [
                  Container(
                    width: AppSize.entryIcon,
                    height: AppSize.entryIcon,
                    decoration: BoxDecoration(
                      color: c.primary,
                      borderRadius: AppRadius.smAll,
                    ),
                    child: Icon(
                      Icons.search_rounded,
                      size: AppSize.icon,
                      color: c.onPrimary,
                    ),
                  ),
                  const SizedBox(width: AppSpace.sm),
                  Expanded(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          l10n.searchTitle,
                          style: AppType.label.copyWith(color: c.ink),
                        ),
                        const SizedBox(height: AppSpace.xxs / 2),
                        Text(
                          l10n.searchEntryHint,
                          style: AppType.body.copyWith(color: c.inkSoft),
                        ),
                      ],
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
