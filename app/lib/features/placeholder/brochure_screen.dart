// PLACEHOLDER — to be replaced by the designer.
//
// Deliberately bare: page URLs (resolved) and, when present, product names
// with prices. No images are loaded.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/data.dart';
import '../../l10n/app_localizations.dart';

class BrochureScreen extends ConsumerWidget {
  const BrochureScreen({super.key, required this.brochureId});

  final String brochureId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final brochure = ref.watch(brochureProvider(brochureId)).value;
    final repository = ref.watch(catalogRepositoryProvider);

    if (brochure == null) {
      return Scaffold(
        appBar: AppBar(),
        body: Center(child: Text(l10n.noBrochures)),
      );
    }

    return Scaffold(
      appBar: AppBar(title: Text(brochure.title)),
      body: ListView(
        children: [
          if (brochure.hasPages) ...[
            ListTile(title: Text(l10n.pageCount(brochure.pages.length))),
            for (final page in brochure.pages)
              ListTile(title: Text(repository.resolve(page.url).toString())),
          ],
          if (brochure.hasProducts) ...[
            ListTile(title: Text(l10n.productsTitle)),
            ..._products(ref, l10n),
          ],
        ],
      ),
    );
  }

  List<Widget> _products(WidgetRef ref, AppLocalizations l10n) {
    return ref
        .watch(productsProvider(brochureId))
        .when(
          loading: () => [ListTile(title: Text(l10n.loading))],
          error: (error, _) => [ListTile(title: Text(l10n.loadError))],
          data: (file) => [
            for (final product in file.products)
              ListTile(
                title: Text(product.name),
                subtitle: Text(product.quantityText ?? ''),
                trailing: Text(product.price.format()),
              ),
          ],
        );
  }
}
