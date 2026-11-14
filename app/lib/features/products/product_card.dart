import 'package:flutter/material.dart';

import '../../data/data.dart';
import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../../design/typography.dart';
import '../../design/widgets/app_buttons.dart';
import '../../design/widgets/catalog_image.dart';
import '../../design/widgets/feedback.dart';
import '../../l10n/app_localizations.dart';

/// One priced product: name, brand and amount, a big price, the earlier
/// price crossed out and the discount when the market printed them.
class ProductCard extends StatelessWidget {
  const ProductCard({super.key, required this.product, this.onShowPage});

  final Product product;

  /// Opens the brochure page that shows this product; null hides the button.
  final VoidCallback? onShowPage;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    final oldPrice = product.oldPrice;
    final discount = product.discountPercent;
    final brand = product.brand?.trim() ?? '';
    final quantity = product.quantityText?.trim() ?? '';
    final facts = brand.isNotEmpty && quantity.isNotEmpty
        ? l10n.pairWithDot(brand, quantity)
        : '$brand$quantity';

    final details = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(product.name, style: AppType.title.copyWith(color: c.ink)),
        if (facts.isNotEmpty) ...[
          const SizedBox(height: AppSpace.xxs),
          Text(facts, style: AppType.body.copyWith(color: c.inkSoft)),
        ],
        const SizedBox(height: AppSpace.xs),
        Wrap(
          spacing: AppSpace.sm,
          runSpacing: AppSpace.xxs,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text(
              product.price.format(),
              style: AppType.price.copyWith(color: c.ink),
            ),
            if (oldPrice != null)
              Semantics(
                label: l10n.oldPriceSpoken(oldPrice.format()),
                excludeSemantics: true,
                child: Text(
                  oldPrice.format(),
                  style: AppType.priceOld.copyWith(
                    color: c.inkSoft,
                    decorationColor: c.inkSoft,
                  ),
                ),
              ),
            if (discount != null) Pill(text: l10n.discountPercent(discount)),
          ],
        ),
      ],
    );

    return AppCard(
      padding: const EdgeInsets.all(AppSpace.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          MergeSemantics(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (product.image != null) ...[
                  ClipRRect(
                    borderRadius: AppRadius.smAll,
                    child: SizedBox.square(
                      dimension: AppSize.productImage,
                      child: ColoredBox(
                        color: c.logoPlate,
                        child: CatalogImage(
                          url: product.image,
                          fit: BoxFit.contain,
                          logicalWidth: AppSize.productImage,
                          placeholder: const CoverPlaceholder(
                            icon: Icons.shopping_basket_rounded,
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: AppSpace.md),
                ],
                Expanded(child: details),
              ],
            ),
          ),
          if (onShowPage != null) ...[
            const SizedBox(height: AppSpace.sm),
            Align(
              alignment: Alignment.centerLeft,
              child: AppButton(
                label: l10n.showOnPage,
                icon: Icons.menu_book_rounded,
                kind: AppButtonKind.tonal,
                minHeight: AppSize.touch,
                onPressed: onShowPage,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
