// PLACEHOLDER — to be replaced by the designer.
//
// Deliberately bare: lists chains from orderedChainsProvider to prove the
// data flow. No styling effort; do not build on this.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/data.dart';
import '../../l10n/app_localizations.dart';
import 'chain_screen.dart';

class ChainListScreen extends ConsumerWidget {
  const ChainListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final chains = ref.watch(orderedChainsProvider);
    final isStale = ref.watch(catalogProvider).value?.isStale ?? false;
    final updateRequired = ref.watch(appUpdateRequiredProvider);

    return Scaffold(
      appBar: AppBar(title: Text(l10n.chainsTitle)),
      body: chains.when(
        loading: () => Center(child: Text(l10n.loading)),
        error: (error, _) => Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(l10n.loadError),
              TextButton(
                onPressed: () => ref.read(catalogProvider.notifier).refresh(),
                child: Text(l10n.retry),
              ),
            ],
          ),
        ),
        data: (chains) => RefreshIndicator(
          onRefresh: () => ref.read(catalogProvider.notifier).refresh(),
          child: ListView(
            children: [
              if (updateRequired) ListTile(title: Text(l10n.updateRequired)),
              if (isStale) ListTile(title: Text(l10n.staleNotice)),
              for (final chain in chains) _ChainTile(chain: chain),
            ],
          ),
        ),
      ),
    );
  }
}

class _ChainTile extends ConsumerWidget {
  const _ChainTile({required this.chain});

  final Chain chain;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final summary = ref.watch(chainSummaryProvider(chain.id)).value;
    final isFavorite = ref.watch(isFavoriteProvider(chain.id));
    return ListTile(
      title: Text(chain.name),
      subtitle: Row(
        children: [
          if (chain.isWebView) const Icon(Icons.public),
          if (summary != null && !chain.isWebView)
            Text('${summary.currentCount}'),
          if (summary?.isNew ?? false) const Icon(Icons.fiber_new),
          if (chain.isStale) const Icon(Icons.cloud_off),
        ],
      ),
      trailing: IconButton(
        icon: Icon(isFavorite ? Icons.star : Icons.star_border),
        onPressed: () => ref.read(favoritesProvider.notifier).toggle(chain.id),
      ),
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute<void>(builder: (_) => ChainScreen(chainId: chain.id)),
      ),
    );
  }
}
