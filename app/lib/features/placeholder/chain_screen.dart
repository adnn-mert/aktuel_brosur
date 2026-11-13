// PLACEHOLDER — to be replaced by the designer.
//
// Deliberately bare: one chain's brochures grouped by brochureGroupsProvider.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/data.dart';
import '../../l10n/app_localizations.dart';
import 'brochure_screen.dart';

class ChainScreen extends ConsumerWidget {
  const ChainScreen({super.key, required this.chainId});

  final String chainId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final chain = ref.watch(chainProvider(chainId)).value;
    final groups = ref.watch(brochureGroupsProvider(chainId));
    final today = ref.watch(clockProvider).today();

    return Scaffold(
      appBar: AppBar(title: Text(chain?.name ?? '')),
      body: groups.when(
        loading: () => Center(child: Text(l10n.loading)),
        error: (error, _) => Center(child: Text(l10n.loadError)),
        data: (groups) {
          if (chain != null && chain.isWebView) {
            return ListTile(
              title: Text(l10n.openChainWebsite),
              subtitle: Text(chain.webUrl),
            );
          }
          if (groups.isEmpty) return Center(child: Text(l10n.noBrochures));
          return ListView(
            children: [
              for (final (title, items) in [
                (l10n.sectionCurrent, groups.current),
                (l10n.sectionUpcoming, groups.upcoming),
                (l10n.sectionPast, groups.past),
              ])
                if (items.isNotEmpty) ...[
                  ListTile(title: Text(title)),
                  for (final brochure in items)
                    ListTile(
                      title: Text(brochure.title),
                      subtitle: Text(formatBrochureDates(brochure, today)),
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) =>
                              BrochureScreen(brochureId: brochure.id),
                        ),
                      ),
                    ),
                ],
            ],
          );
        },
      ),
    );
  }
}
