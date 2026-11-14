import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/data.dart';
import '../../design/tokens.dart';
import '../../design/widgets/app_buttons.dart';
import '../../design/widgets/app_scaffold.dart';
import '../../design/widgets/chain_mark.dart';
import '../../design/widgets/feedback.dart';
import '../../l10n/app_localizations.dart';
import '../app/navigation.dart';
import 'brochure_card.dart';

/// One market: its brochures under "Bu hafta", "Gelecek hafta" and
/// "Geçmiş broşürler".
class ChainScreen extends ConsumerWidget {
  const ChainScreen({super.key, required this.chainId});

  final String chainId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final chain = ref.watch(chainProvider(chainId)).value;
    final groups = ref.watch(brochureGroupsProvider(chainId));
    final isFavorite = ref.watch(isFavoriteProvider(chainId));

    return AppScaffold(
      topBar: AppTopBar(
        titleWidget: chain == null
            ? null
            : ChainMark(
                chain: chain,
                height: AppSize.topBarMark,
                width: AppSize.topBarMarkWidth,
                radius: AppRadius.smAll,
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpace.sm,
                  vertical: AppSpace.xs,
                ),
              ),
        trailing: chain == null
            ? null
            : FavoriteStar(
                isFavorite: isFavorite,
                label: isFavorite
                    ? l10n.favoriteRemove(chain.name)
                    : l10n.favoriteAdd(chain.name),
                onPressed: () async {
                  final saved = await ref
                      .read(favoritesProvider.notifier)
                      .toggle(chain.id);
                  if (!context.mounted) return;
                  showAppMessage(
                    context,
                    !saved
                        ? l10n.favoriteFailed
                        : isFavorite
                        ? l10n.favoriteRemoved(chain.name)
                        : l10n.favoriteAdded(chain.name),
                  );
                },
              ),
      ),
      body: groups.when(
        loading: () => const _ChainLoading(),
        error: (error, _) => StateView(
          icon: Icons.wifi_off_rounded,
          title: l10n.offlineTitle,
          message: l10n.offlineMessage,
          actionLabel: l10n.retry,
          actionIcon: Icons.refresh_rounded,
          onAction: () => ref.read(catalogProvider.notifier).refresh(),
        ),
        data: (groups) {
          if (chain == null) {
            return StateView(
              icon: Icons.storefront_rounded,
              title: l10n.unknownChainTitle,
            );
          }
          if (groups.isEmpty) {
            return StateView(
              icon: Icons.menu_book_rounded,
              title: l10n.emptyChainTitle,
              message: l10n.emptyChainMessage(chain.name),
              actionLabel: l10n.openChainWebsite,
              actionIcon: Icons.public_rounded,
              onAction: () => openChainWebsite(context, chain),
            );
          }
          return _BrochureList(chain: chain, groups: groups);
        },
      ),
    );
  }
}

class _BrochureList extends ConsumerWidget {
  const _BrochureList({required this.chain, required this.groups});

  final Chain chain;
  final BrochureGroups groups;

  /// Up to this many current brochures get the large cover.
  static const int _prominentLimit = 2;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final today = ref.watch(clockProvider).today();
    final lastOk = chain.lastOkAt;
    // What started most recently is what the reader came for; a flyer that
    // has been running for months goes below this week's.
    final current = [...groups.current]
      ..sort((a, b) {
        final byStart = (b.validFrom ?? b.firstSeen).compareTo(
          a.validFrom ?? a.firstSeen,
        );
        return byStart != 0 ? byStart : a.id.compareTo(b.id);
      });

    List<Widget> section(
      String title,
      List<Brochure> items, {
      bool prominent = false,
      bool badges = false,
    }) => [
      if (items.isNotEmpty) ...[
        SectionHeader(title: title),
        for (final brochure in items) ...[
          BrochureCard(
            key: ValueKey('brochure-${brochure.id}'),
            brochure: brochure,
            prominent: prominent,
            showNewBadge: badges && isBrochureNew(brochure, today),
            onOpen: () => openBrochure(context, brochure.id),
          ),
          const SizedBox(height: AppSpace.sm),
        ],
      ],
    ];

    return ListView(
      padding: const EdgeInsets.fromLTRB(
        AppSpace.screen,
        0,
        AppSpace.screen,
        AppSpace.xxl,
      ),
      children: [
        ContentWidth(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (chain.isStale) ...[
                const SizedBox(height: AppSpace.md),
                NoticeStrip(
                  icon: Icons.cloud_off_rounded,
                  text: l10n.chainStaleNotice,
                  detail: lastOk == null
                      ? l10n.chainStaleDetailUndated
                      : l10n.chainStaleDetail(lastOk.toLocal()),
                ),
              ],
              ...section(
                l10n.sectionCurrent,
                current,
                // A big cover is an invitation; with many brochures it only
                // makes the list long.
                prominent: current.length <= _prominentLimit,
                badges: true,
              ),
              ...section(l10n.sectionUpcoming, groups.upcoming, badges: true),
              ...section(l10n.sectionPast, groups.past),
            ],
          ),
        ),
      ],
    );
  }
}

class _ChainLoading extends StatelessWidget {
  const _ChainLoading();

  static const int _rows = 3;
  static const double _rowHeight = AppSize.coverHero;

  @override
  Widget build(BuildContext context) => ListView(
    physics: const NeverScrollableScrollPhysics(),
    padding: const EdgeInsets.all(AppSpace.screen),
    children: [
      for (var i = 0; i < _rows; i++) ...[
        const SkeletonBox(height: _rowHeight),
        const SizedBox(height: AppSpace.sm),
      ],
    ],
  );
}
