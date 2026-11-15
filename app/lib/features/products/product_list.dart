import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/data.dart';
import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../../design/typography.dart';
import '../../design/widgets/app_scaffold.dart';
import '../../design/widgets/feedback.dart';
import '../../l10n/app_localizations.dart';
import 'product_card.dart';

/// The priced product list of a brochure, in the market's own order.
class ProductList extends ConsumerWidget {
  const ProductList({
    super.key,
    required this.brochure,
    this.onShowPage,
    this.highlight,
  });

  final Brochure brochure;

  /// The product the user came for (from the search). It is shown first,
  /// under its own heading, and again at its place in the list below.
  /// Ignored when the list of the brochure no longer contains it.
  final Product? highlight;

  /// Called with a 0-based page index when "Sayfada göster" is pressed.
  /// Null (or a brochure without pages) hides those buttons.
  final ValueChanged<int>? onShowPage;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    final products = ref.watch(productsProvider(brochure.id));

    return products.when(
      loading: () => Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpace.xl),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SizedBox.square(
                dimension: AppSize.touch,
                child: CircularProgressIndicator(strokeWidth: AppSpace.xxs),
              ),
              const SizedBox(height: AppSpace.md),
              Text(
                l10n.productsLoading,
                textAlign: TextAlign.center,
                style: AppType.body.copyWith(color: c.inkSoft),
              ),
            ],
          ),
        ),
      ),
      error: (error, _) => StateView(
        icon: Icons.wifi_off_rounded,
        title: l10n.productsErrorTitle,
        message: error is CatalogFormatException
            ? l10n.brokenMessage
            : l10n.checkConnection,
        actionLabel: l10n.retry,
        actionIcon: Icons.refresh_rounded,
        onAction: () => ref.invalidate(productsProvider(brochure.id)),
      ),
      data: (file) {
        if (file.products.isEmpty) {
          return StateView(
            icon: Icons.format_list_bulleted_rounded,
            title: l10n.productsEmptyTitle,
          );
        }
        final canShowPages = onShowPage != null && brochure.hasPages;
        VoidCallback? showPageOf(Product product) {
          final pageIndex = product.pageIndex;
          final hasPage =
              canShowPages &&
              pageIndex != null &&
              pageIndex < brochure.pages.length;
          return hasPage ? () => onShowPage!(pageIndex) : null;
        }

        final wanted = highlight;
        final pinned = wanted != null && file.products.contains(wanted)
            ? wanted
            : null;
        return ListView.builder(
          padding: const EdgeInsets.fromLTRB(
            AppSpace.screen,
            AppSpace.md,
            AppSpace.screen,
            AppSpace.xxl,
          ),
          itemCount: file.products.length + 1,
          itemBuilder: (context, index) {
            if (index == 0) {
              final count = Text(
                l10n.productCount(file.products.length),
                style: AppType.body.copyWith(color: c.inkSoft),
              );
              return ContentWidth(
                child: Padding(
                  padding: const EdgeInsets.only(bottom: AppSpace.sm),
                  child: pinned == null
                      ? Align(alignment: Alignment.centerLeft, child: count)
                      : Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Semantics(
                              header: true,
                              child: Text(
                                l10n.searchedProductTitle,
                                style: AppType.section.copyWith(color: c.ink),
                              ),
                            ),
                            const SizedBox(height: AppSpace.sm),
                            ProductCard(
                              key: const ValueKey('searched-product'),
                              product: pinned,
                              highlighted: true,
                              onShowPage: showPageOf(pinned),
                            ),
                            const SizedBox(height: AppSpace.xl),
                            Semantics(
                              header: true,
                              child: Text(
                                l10n.allProductsTitle,
                                style: AppType.section.copyWith(color: c.ink),
                              ),
                            ),
                            const SizedBox(height: AppSpace.xxs),
                            count,
                          ],
                        ),
                ),
              );
            }
            final product = file.products[index - 1];
            return ContentWidth(
              child: Padding(
                padding: const EdgeInsets.only(bottom: AppSpace.sm),
                child: ProductCard(
                  product: product,
                  onShowPage: showPageOf(product),
                ),
              ),
            );
          },
        );
      },
    );
  }
}
