import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/data.dart';
import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../../design/typography.dart';
import '../../design/widgets/app_buttons.dart';
import '../../design/widgets/app_scaffold.dart';
import '../../design/widgets/feedback.dart';
import '../../design/widgets/logo_mark.dart';
import '../../l10n/app_localizations.dart';
import '../app/navigation.dart';
import 'chain_card.dart';

/// Home: "which market shall we look at?" and the markets as big cards.
/// No menu, no tabs; one job.
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final chains = ref.watch(orderedChainsProvider);
    return AppScaffold(
      body: chains.when(
        loading: () => const _HomeLoading(),
        error: (error, _) => _HomeError(error: error),
        data: (chains) => _HomeContent(chains: chains),
      ),
    );
  }
}

class _HomeHeader extends ConsumerWidget {
  const _HomeHeader();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    final today = ref.watch(clockProvider).today();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const ExcludeSemantics(child: LogoMark(size: AppSize.headerLogo)),
            const SizedBox(width: AppSpace.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    l10n.appTitle,
                    style: AppType.wordmark.copyWith(color: c.ink),
                  ),
                  Text(
                    l10n.homeToday(today),
                    style: AppType.body.copyWith(color: c.inkSoft),
                  ),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpace.xl),
        Semantics(
          header: true,
          child: Text(
            l10n.homeQuestion,
            style: AppType.headline.copyWith(color: c.ink),
          ),
        ),
      ],
    );
  }
}

class _HomeContent extends ConsumerWidget {
  const _HomeContent({required this.chains});

  final List<Chain> chains;

  Future<void> _toggleFavorite(
    BuildContext context,
    WidgetRef ref,
    Chain chain,
  ) async {
    final l10n = AppLocalizations.of(context);
    final wasFavorite = ref.read(isFavoriteProvider(chain.id));
    final saved = await ref.read(favoritesProvider.notifier).toggle(chain.id);
    if (!context.mounted) return;
    showAppMessage(
      context,
      !saved
          ? l10n.favoriteFailed
          : wasFavorite
          ? l10n.favoriteRemoved(chain.name)
          : l10n.favoriteAdded(chain.name),
    );
  }

  Future<void> _refresh(BuildContext context, WidgetRef ref) async {
    final l10n = AppLocalizations.of(context);
    final outcome = await ref.read(catalogProvider.notifier).refresh();
    if (!context.mounted) return;
    showAppMessage(context, switch (outcome) {
      RefreshOutcome.updated => l10n.refreshUpdated,
      RefreshOutcome.offline => l10n.refreshOffline,
      RefreshOutcome.failed => l10n.refreshFailed,
    });
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final catalog = ref.watch(catalogProvider).value;
    final updateRequired = ref.watch(appUpdateRequiredProvider);
    final favoriteIds = ref.watch(favoritesProvider).value ?? const <String>{};

    final favorites = [
      for (final chain in chains)
        if (favoriteIds.contains(chain.id)) chain,
    ];
    final others = [
      for (final chain in chains)
        if (!favoriteIds.contains(chain.id)) chain,
    ];

    Widget grid(List<Chain> items) => ChainGrid(
      chains: items,
      onOpen: (chain) => openChain(context, ref, chain),
      onToggleFavorite: (chain) => _toggleFavorite(context, ref, chain),
    );

    return RefreshIndicator(
      onRefresh: () => _refresh(context, ref),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(
          AppSpace.screen,
          AppSpace.lg,
          AppSpace.screen,
          AppSpace.xxl,
        ),
        children: [
          ContentWidth(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const _HomeHeader(),
                if (updateRequired) ...[
                  const SizedBox(height: AppSpace.md),
                  NoticeStrip(
                    icon: Icons.system_update_rounded,
                    text: l10n.updateRequired,
                    detail: l10n.updateRequiredDetail,
                  ),
                ],
                if (catalog?.isStale ?? false) ...[
                  const SizedBox(height: AppSpace.md),
                  NoticeStrip(
                    icon: Icons.wifi_off_rounded,
                    text: l10n.staleNotice,
                    detail: l10n.staleDetail(catalog!.fetchedAt.toLocal()),
                  ),
                ],
                if (favorites.isEmpty) ...[
                  const SizedBox(height: AppSpace.xl),
                  grid(others),
                  const SizedBox(height: AppSpace.xl),
                  _FavoriteHint(text: l10n.homeFavoriteHint),
                ] else ...[
                  SectionHeader(
                    title: l10n.homeFavorites,
                    icon: Icons.star_rounded,
                  ),
                  const SizedBox(height: AppSpace.xs),
                  grid(favorites),
                  if (others.isNotEmpty) ...[
                    SectionHeader(title: l10n.homeOthers),
                    const SizedBox(height: AppSpace.xs),
                    grid(others),
                  ],
                ],
                const SizedBox(height: AppSpace.xl),
                AppButton(
                  label: l10n.homeRefresh,
                  icon: Icons.refresh_rounded,
                  kind: AppButtonKind.outline,
                  expand: true,
                  onPressed: () => _refresh(context, ref),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _FavoriteHint extends StatelessWidget {
  const _FavoriteHint({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ExcludeSemantics(
          child: Icon(
            Icons.star_outline_rounded,
            size: AppSize.icon,
            color: c.inkSoft,
          ),
        ),
        const SizedBox(width: AppSpace.xs),
        Expanded(
          child: Text(text, style: AppType.body.copyWith(color: c.inkSoft)),
        ),
      ],
    );
  }
}

/// Two columns of market cards; rows share one height. With a very large
/// system font it becomes a single column so words are never broken.
class ChainGrid extends StatelessWidget {
  const ChainGrid({
    super.key,
    required this.chains,
    required this.onOpen,
    required this.onToggleFavorite,
  });

  final List<Chain> chains;
  final ValueChanged<Chain> onOpen;
  final ValueChanged<Chain> onToggleFavorite;

  @override
  Widget build(BuildContext context) {
    final columns = context.useStackedBars ? 1 : 2;
    final rows = <Widget>[];
    for (var i = 0; i < chains.length; i += columns) {
      final cells = <Widget>[];
      for (var j = 0; j < columns; j++) {
        if (j > 0) cells.add(const SizedBox(width: AppSpace.grid));
        final index = i + j;
        cells.add(
          Expanded(
            child: index < chains.length
                ? ChainCard(
                    key: ValueKey('chain-${chains[index].id}'),
                    chain: chains[index],
                    onOpen: () => onOpen(chains[index]),
                    onToggleFavorite: () => onToggleFavorite(chains[index]),
                  )
                : const SizedBox.shrink(),
          ),
        );
      }
      if (rows.isNotEmpty) {
        rows.add(
          const SizedBox(height: AppSpace.grid + ChainCard.stickerOverhang),
        );
      }
      rows.add(
        IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: cells,
          ),
        ),
      );
    }
    return Column(children: rows);
  }
}

class _HomeLoading extends StatelessWidget {
  const _HomeLoading();

  static const int _skeletonRows = 3;
  static const double _skeletonHeight =
      AppSize.chainPlate + AppSize.touch + AppSpace.md;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    return ListView(
      physics: const NeverScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(
        AppSpace.screen,
        AppSpace.lg,
        AppSpace.screen,
        AppSpace.xxl,
      ),
      children: [
        ContentWidth(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const _HomeHeader(),
              const SizedBox(height: AppSpace.md),
              Semantics(
                liveRegion: true,
                child: Text(
                  l10n.homeLoading,
                  style: AppType.body.copyWith(color: c.inkSoft),
                ),
              ),
              const SizedBox(height: AppSpace.md),
              for (var i = 0; i < _skeletonRows; i++) ...[
                const Row(
                  children: [
                    Expanded(child: SkeletonBox(height: _skeletonHeight)),
                    SizedBox(width: AppSpace.grid),
                    Expanded(child: SkeletonBox(height: _skeletonHeight)),
                  ],
                ),
                const SizedBox(height: AppSpace.grid),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _HomeError extends ConsumerWidget {
  const _HomeError({required this.error});

  final Object error;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final broken = error is CatalogFormatException;
    return StateView(
      art: const LogoMark(size: AppSize.stateArt),
      title: broken ? l10n.brokenTitle : l10n.offlineTitle,
      message: broken ? l10n.brokenMessage : l10n.offlineMessage,
      actionLabel: l10n.retry,
      actionIcon: Icons.refresh_rounded,
      onAction: () => ref.read(catalogProvider.notifier).refresh(),
    );
  }
}
