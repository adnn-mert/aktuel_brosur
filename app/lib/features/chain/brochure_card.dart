import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/data.dart';
import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../../design/typography.dart';
import '../../design/widgets/app_scaffold.dart';
import '../../design/widgets/catalog_image.dart';
import '../../design/widgets/feedback.dart';
import '../../l10n/app_localizations.dart';

/// "8 sayfa", "7 ürün" or "4 sayfa · 14 ürün".
String brochureDetail(AppLocalizations l10n, Brochure brochure) {
  final pages = brochure.hasPages
      ? l10n.pageCount(brochure.pages.length)
      : null;
  final products = brochure.hasProducts && brochure.productCount > 0
      ? l10n.productCount(brochure.productCount)
      : null;
  if (pages != null && products != null) {
    return l10n.pairWithDot(pages, products);
  }
  return pages ?? products ?? '';
}

/// The brochure's title without the date text the card already shows large
/// (BİM titles repeat it: "13 Kasım Cuma Aktüel Ürünler").
String brochureTitleWithoutDate(Brochure brochure) {
  final label = brochure.dateLabel?.trim() ?? '';
  if (label.isEmpty) return brochure.title;
  return brochure.title.replaceFirst(label, '').trim();
}

/// True when [brochure] was first seen today or yesterday.
bool isBrochureNew(Brochure brochure, DateTime today) =>
    daysBetween(dateOnly(brochure.firstSeen.toLocal()), dateOnly(today)) <
    newBadgeDays;

/// One brochure on the market screen: cover on the left, big date, title and
/// size on the right. The whole card opens the brochure.
class BrochureCard extends ConsumerWidget {
  const BrochureCard({
    super.key,
    required this.brochure,
    required this.onOpen,
    this.prominent = false,
    this.showNewBadge = false,
  });

  final Brochure brochure;
  final VoidCallback onOpen;

  /// Larger cover and a filled "Aç" (used under "Bu hafta").
  final bool prominent;

  final bool showNewBadge;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    final today = ref.watch(clockProvider).today();
    final dates = formatBrochureDates(brochure, today);
    final detail = brochureDetail(l10n, brochure);
    final thumbnail = brochure.thumbnail;
    final coverWidth = context.useStackedBars
        ? AppSize.coverCompact
        : prominent
        ? AppSize.coverHero
        : AppSize.cover;
    final heading = dates.isEmpty ? brochure.title : dates;
    final title = brochureTitleWithoutDate(brochure);
    final showTitle = dates.isNotEmpty && title.isNotEmpty && title != dates;

    final spoken = [
      heading,
      if (showTitle) title,
      detail,
      if (showNewBadge) l10n.badgeNew,
      l10n.brochureOpen,
    ].where((s) => s.isNotEmpty).join(', ');

    return AppCard(
      onTap: onOpen,
      semanticLabel: spoken,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: coverWidth,
            child: AspectRatio(
              aspectRatio: thumbnail?.aspectRatio ?? AppSize.pageAspectFallback,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  borderRadius: AppRadius.smAll,
                  border: Border.all(color: c.line, width: AppSize.hairline),
                ),
                position: DecorationPosition.foreground,
                child: ClipRRect(
                  borderRadius: AppRadius.smAll,
                  child: CatalogImage(
                    url: thumbnail?.url,
                    logicalWidth: AppSize.coverHero,
                    placeholder: CoverPlaceholder(
                      icon: brochure.hasPages
                          ? Icons.menu_book_rounded
                          : Icons.format_list_bulleted_rounded,
                    ),
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: AppSpace.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (showNewBadge) ...[
                  Pill(text: l10n.badgeNew),
                  const SizedBox(height: AppSpace.xs),
                ],
                Text(heading, style: AppType.title.copyWith(color: c.ink)),
                if (showTitle) ...[
                  const SizedBox(height: AppSpace.xxs),
                  Text(title, style: AppType.body.copyWith(color: c.inkSoft)),
                ],
                if (detail.isNotEmpty) ...[
                  const SizedBox(height: AppSpace.xxs),
                  Text(detail, style: AppType.body.copyWith(color: c.inkSoft)),
                ],
                const SizedBox(height: AppSpace.sm),
                _OpenCue(label: l10n.open, filled: prominent),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// A button-shaped cue inside the card. It is not a separate target (the
/// whole card is); it only makes "this opens" unmistakable.
class _OpenCue extends StatelessWidget {
  const _OpenCue({required this.label, required this.filled});

  final String label;
  final bool filled;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final background = filled ? c.primary : c.primarySoft;
    final foreground = filled ? c.onPrimary : c.onPrimarySoft;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: background,
        borderRadius: AppRadius.mdAll,
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AppSpace.md,
          AppSpace.xs,
          AppSpace.xs,
          AppSpace.xs,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Flexible(
              child: Text(
                label,
                style: AppType.label.copyWith(color: foreground),
              ),
            ),
            Icon(
              Icons.chevron_right_rounded,
              size: AppSize.icon,
              color: foreground,
            ),
          ],
        ),
      ),
    );
  }
}
