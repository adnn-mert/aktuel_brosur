import 'package:flutter/material.dart';

import '../../data/data.dart';
import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../../design/typography.dart';
import '../../design/widgets/app_buttons.dart';
import '../../design/widgets/catalog_image.dart';
import '../../design/widgets/feedback.dart';
import '../../l10n/app_localizations.dart';

/// One priced product.
///
/// Three prices can meet on a card and each has its own visual language so
/// none can be taken for another (DESIGN.md, section 14):
///
/// * the **shelf price**: what everyone pays today. Always the largest
///   number, plain ink, never crossed out;
/// * the **old price**: small, soft and crossed out, with a "%20 indirim"
///   pill;
/// * the **member price**: inside a framed green tag together with its label
///   ("Money ile"). It never appears without the label and never replaces the
///   shelf price.
///
/// A unit note ("kg fiyatı") is glued to every price it applies to.
class ProductCard extends StatelessWidget {
  const ProductCard({
    super.key,
    required this.product,
    this.onShowPage,
    this.highlighted = false,
  });

  final Product product;

  /// Opens the brochure page that shows this product; null hides the button.
  final VoidCallback? onShowPage;

  /// Frames the card in the action colour: the product the user came here
  /// for (from the search). The frame is extra; the heading above it says so
  /// in words.
  final bool highlighted;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);

    final card = AppCard(
      padding: const EdgeInsets.all(AppSpace.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          MergeSemantics(child: ProductFacts(product: product)),
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
    if (!highlighted) return card;
    return DecoratedBox(
      position: DecorationPosition.foreground,
      decoration: BoxDecoration(
        borderRadius: AppRadius.lgAll,
        border: Border.all(color: c.primary, width: AppSize.focusRing),
      ),
      child: card,
    );
  }
}

/// What a product is and what it costs: photo, name, brand and the prices.
/// The one place the price language of section 14 is drawn, so a product
/// looks the same in a brochure's list and in the search results.
class ProductFacts extends StatelessWidget {
  const ProductFacts({super.key, required this.product});

  final Product product;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    final oldPrice = product.oldPrice;
    final discount = product.discountPercent;
    final brand = product.brand?.trim() ?? '';
    final unit = product.quantityText?.trim() ?? '';
    final memberPrice = product.memberPrice;
    final memberLabel = product.memberPriceLabel;

    final details = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(product.name, style: AppType.title.copyWith(color: c.ink)),
        if (brand.isNotEmpty) ...[
          const SizedBox(height: AppSpace.xxs),
          Text(brand, style: AppType.body.copyWith(color: c.inkSoft)),
        ],
        const SizedBox(height: AppSpace.xs),
        Wrap(
          spacing: AppSpace.sm,
          runSpacing: AppSpace.xxs,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            PriceWithUnit(
              key: const ValueKey('shelf-price'),
              price: product.price.format(),
              unit: unit,
              priceStyle: AppType.price.copyWith(color: c.ink),
              unitStyle: AppType.bodyStrong.copyWith(color: c.ink),
            ),
            if (oldPrice != null)
              Semantics(
                label: l10n.oldPriceSpoken(oldPrice.format()),
                excludeSemantics: true,
                child: Text(
                  oldPrice.format(),
                  key: const ValueKey('old-price'),
                  style: AppType.priceOld.copyWith(
                    color: c.inkSoft,
                    decorationColor: c.inkSoft,
                  ),
                ),
              ),
            if (discount != null) Pill(text: l10n.discountPercent(discount)),
          ],
        ),
        if (memberPrice != null && memberLabel != null) ...[
          const SizedBox(height: AppSpace.xs),
          MemberPriceTag(
            label: memberLabel,
            price: memberPrice.format(),
            unit: unit,
          ),
        ],
      ],
    );

    return Row(
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
    );
  }
}

/// A price with the note that says what it is the price of ("kg fiyatı").
/// The two are one unit: laid out together, wrapped together, read together
/// by a screen reader. With an empty [unit] it is just the price.
class PriceWithUnit extends StatelessWidget {
  const PriceWithUnit({
    super.key,
    required this.price,
    required this.unit,
    required this.priceStyle,
    required this.unitStyle,
  });

  final String price;
  final String unit;
  final TextStyle priceStyle;
  final TextStyle unitStyle;

  @override
  Widget build(BuildContext context) {
    final priceText = Text(price, style: priceStyle);
    if (unit.isEmpty) return priceText;
    return Semantics(
      label: AppLocalizations.of(context).priceWithUnit(price, unit),
      excludeSemantics: true,
      child: Wrap(
        spacing: AppSpace.xs,
        crossAxisAlignment: WrapCrossAlignment.end,
        children: [
          priceText,
          Padding(
            // Sits on the price's baseline rather than under its descender.
            padding: const EdgeInsets.only(bottom: AppSpace.xxs / 2),
            child: Text(unit, style: unitStyle),
          ),
        ],
      ),
    );
  }
}

/// The card-holder price: a framed tag that carries its own label, so the
/// number can never be read as the price everyone pays.
class MemberPriceTag extends StatelessWidget {
  const MemberPriceTag({
    super.key,
    required this.label,
    required this.price,
    this.unit = '',
  });

  /// Who gets this price, in the market's words ("Money ile").
  final String label;
  final String price;
  final String unit;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    final spokenPrice = unit.isEmpty ? price : l10n.priceWithUnit(price, unit);
    return Semantics(
      label: l10n.memberPriceSpoken(label, spokenPrice),
      excludeSemantics: true,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: c.primarySoft,
          borderRadius: AppRadius.smAll,
          border: Border.all(color: c.primary, width: AppSize.outline),
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpace.sm,
            vertical: AppSpace.xs,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.card_membership_rounded,
                    size: AppSize.iconSmall,
                    color: c.onPrimarySoft,
                  ),
                  const SizedBox(width: AppSpace.xs),
                  Flexible(
                    child: Text(
                      label,
                      style: AppType.bodyStrong.copyWith(
                        color: c.onPrimarySoft,
                      ),
                    ),
                  ),
                ],
              ),
              PriceWithUnit(
                price: price,
                unit: unit,
                priceStyle: AppType.memberPrice.copyWith(
                  color: c.onPrimarySoft,
                ),
                unitStyle: AppType.bodyStrong.copyWith(color: c.onPrimarySoft),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
