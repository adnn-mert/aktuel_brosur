import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/data.dart';
import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../../design/typography.dart';
import '../../design/widgets/app_buttons.dart';
import '../../design/widgets/chain_mark.dart';
import '../../design/widgets/feedback.dart';
import '../../l10n/app_localizations.dart';

/// The two status lines under a market's logo.
({String first, String? second}) chainStatusLines(
  AppLocalizations l10n,
  ChainSummary? summary,
) {
  if (summary == null) return (first: '', second: null);
  if (summary.isWebView) return (first: l10n.cardWeb, second: null);
  if (summary.currentCount > 0) {
    return (
      first: l10n.cardCurrent,
      second: l10n.brochureCount(summary.currentCount),
    );
  }
  if (summary.upcomingCount > 0) {
    return (
      first: l10n.cardUpcoming,
      second: l10n.brochureCount(summary.upcomingCount),
    );
  }
  if (summary.pastCount > 0) {
    return (
      first: l10n.cardPast,
      second: l10n.brochureCount(summary.pastCount),
    );
  }
  return (first: l10n.cardEmpty, second: null);
}

/// One market on the home screen: logo plate (or name card) on top, status
/// and the favourite star below. The whole card opens the market; only the
/// star is a separate target.
class ChainCard extends ConsumerWidget {
  const ChainCard({
    super.key,
    required this.chain,
    required this.onOpen,
    required this.onToggleFavorite,
  });

  final Chain chain;
  final VoidCallback onOpen;
  final VoidCallback onToggleFavorite;

  /// How far the "Yeni" sticker hangs over the card's top edge.
  static const double stickerOverhang = 10;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    final summary = ref.watch(chainSummaryProvider(chain.id)).value;
    final isFavorite = ref.watch(isFavoriteProvider(chain.id));
    final status = chainStatusLines(l10n, summary);
    final isNew = summary?.isNew ?? false;
    final isStale = summary?.isStale ?? false;

    final spoken = [
      chain.name,
      status.first,
      ?status.second,
      if (isNew) l10n.cardNewSpoken,
      if (isStale) l10n.cardStaleSpoken,
    ].where((s) => s.isNotEmpty).join(', ');

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
        child: Stack(
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ExcludeSemantics(
                  child: ChainMark(
                    chain: chain,
                    radius: BorderRadius.zero,
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpace.md,
                      vertical: AppSpace.lg,
                    ),
                  ),
                ),
                ConstrainedBox(
                  constraints: const BoxConstraints(
                    minHeight: AppSize.touch + AppSpace.xs * 2,
                  ),
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(
                      AppSpace.sm,
                      AppSpace.xs,
                      // Room for the star, which is laid over this corner.
                      AppSize.touch + AppSpace.xs,
                      AppSpace.xs,
                    ),
                    child: Align(
                      alignment: Alignment.centerLeft,
                      child: ExcludeSemantics(
                        child: _StatusLines(
                          first: status.first,
                          second: status.second,
                          isStale: isStale,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
            // The whole card is one button...
            Positioned.fill(
              child: Semantics(
                button: true,
                label: spoken,
                child: InkWell(onTap: onOpen),
              ),
            ),
            // ...except the star, which sits above it.
            Positioned(
              right: AppSpace.xxs,
              bottom: AppSpace.xs,
              child: FavoriteStar(
                isFavorite: isFavorite,
                label: isFavorite
                    ? l10n.favoriteRemove(chain.name)
                    : l10n.favoriteAdd(chain.name),
                onPressed: onToggleFavorite,
              ),
            ),
          ],
        ),
      ),
    );

    if (!isNew) return card;
    return Stack(
      clipBehavior: Clip.none,
      children: [
        card,
        Positioned(
          left: AppSpace.sm,
          top: -stickerOverhang,
          child: ExcludeSemantics(child: Pill(text: l10n.badgeNew)),
        ),
      ],
    );
  }
}

class _StatusLines extends StatelessWidget {
  const _StatusLines({
    required this.first,
    required this.second,
    required this.isStale,
  });

  final String first;
  final String? second;
  final bool isStale;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(first, style: AppType.bodyStrong.copyWith(color: c.ink)),
        if (second != null || isStale)
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (isStale) ...[
                Icon(
                  Icons.cloud_off_rounded,
                  size: AppSize.iconSmall,
                  color: c.inkSoft,
                ),
                const SizedBox(width: AppSpace.xxs),
              ],
              if (second != null)
                Flexible(
                  child: Text(
                    second!,
                    style: AppType.body.copyWith(color: c.inkSoft),
                  ),
                ),
            ],
          ),
      ],
    );
  }
}
