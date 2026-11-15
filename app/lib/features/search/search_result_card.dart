import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/data.dart';
import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../../design/typography.dart';
import '../../design/widgets/app_scaffold.dart';
import '../../design/widgets/chain_mark.dart';
import '../../design/widgets/feedback.dart';
import '../../l10n/app_localizations.dart';
import '../products/product_card.dart';

/// True when [brochure] starts on a later day than [today]: its prices are
/// not valid yet, and a result from it has to say so.
bool startsLater(Brochure brochure, DateTime today) {
  final from = brochure.validFrom;
  return from != null && dateOnly(from).isAfter(dateOnly(today));
}

/// One search result. Top: the product exactly as its brochure's own list
/// shows it ([ProductFacts], so the price rules of DESIGN.md section 14 hold
/// here by construction). Bottom: where the price comes from (which market,
/// which dates) and an "Aç" cue. The whole card opens the brochure.
class SearchResultCard extends ConsumerWidget {
  const SearchResultCard({super.key, required this.hit, required this.onOpen});

  final SearchHit hit;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    final today = ref.watch(clockProvider).today();
    final product = hit.product;
    final dates = formatBrochureDates(hit.brochure, today);
    final upcoming = startsLater(hit.brochure, today);

    final unit = product.quantityText?.trim() ?? '';
    final price = product.price.format();
    final oldPrice = product.oldPrice;
    final memberPrice = product.memberPrice;
    final memberLabel = product.memberPriceLabel;
    final spoken = [
      product.name,
      product.brand?.trim() ?? '',
      unit.isEmpty ? price : l10n.priceWithUnit(price, unit),
      if (oldPrice != null) l10n.oldPriceSpoken(oldPrice.format()),
      if (memberPrice != null && memberLabel != null)
        l10n.memberPriceSpoken(
          memberLabel,
          unit.isEmpty
              ? memberPrice.format()
              : l10n.priceWithUnit(memberPrice.format(), unit),
        ),
      hit.chain.name,
      dates,
      if (upcoming) l10n.searchUpcoming,
      l10n.searchOpenSpoken,
    ].where((s) => s.isNotEmpty).join(', ');

    return AppCard(
      onTap: onOpen,
      semanticLabel: spoken,
      padding: const EdgeInsets.all(AppSpace.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          ProductFacts(product: product),
          const SizedBox(height: AppSpace.sm),
          ColoredBox(
            color: c.line,
            child: const SizedBox(height: AppSize.hairline),
          ),
          const SizedBox(height: AppSpace.sm),
          _Source(chain: hit.chain, dates: dates, upcoming: upcoming),
        ],
      ),
    );
  }
}

/// Which market printed the price and for which days.
class _Source extends StatelessWidget {
  const _Source({
    required this.chain,
    required this.dates,
    required this.upcoming,
  });

  final Chain chain;
  final String dates;
  final bool upcoming;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);

    final where = Row(
      children: [
        ChainMark(
          chain: chain,
          height: AppSize.resultMark,
          width: AppSize.resultMarkWidth,
          radius: AppRadius.smAll,
          padding: const EdgeInsets.all(AppSpace.xs),
        ),
        const SizedBox(width: AppSpace.sm),
        Expanded(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                chain.name,
                key: const ValueKey('result-chain'),
                style: AppType.bodyStrong.copyWith(color: c.ink),
              ),
              if (dates.isNotEmpty)
                Text(
                  dates,
                  key: const ValueKey('result-dates'),
                  style: AppType.body.copyWith(color: c.inkSoft),
                ),
              if (upcoming) ...[
                const SizedBox(height: AppSpace.xxs),
                Pill(
                  text: l10n.searchUpcoming,
                  background: c.notice,
                  foreground: c.onNotice,
                ),
              ],
            ],
          ),
        ),
      ],
    );
    final cue = OpenCue(label: l10n.open);

    return LayoutBuilder(
      builder: (context, constraints) {
        final oneRow =
            !context.useStackedBars &&
            constraints.maxWidth >= AppSize.resultRowMinWidth;
        if (oneRow) {
          return Row(
            children: [
              Expanded(child: where),
              const SizedBox(width: AppSpace.sm),
              cue,
            ],
          );
        }
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            where,
            const SizedBox(height: AppSpace.sm),
            cue,
          ],
        );
      },
    );
  }
}
