/// How a market shows itself: its logo on a plate, or (when the app has no
/// logo file for it) its name written large on its brand colour.
library;

import 'package:flutter/material.dart';

import '../../data/data.dart';
import '../chain_logos.dart';
import '../theme.dart';
import '../tokens.dart';
import '../typography.dart';

class ChainMark extends StatelessWidget {
  const ChainMark({
    super.key,
    required this.chain,
    this.height = AppSize.chainPlate,
    this.width,
    this.radius = AppRadius.mdAll,
    this.padding = const EdgeInsets.all(AppSpace.md),
  });

  final Chain chain;
  final double height;

  /// Null fills the available width.
  final double? width;
  final BorderRadius radius;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final logo = chainLogos[chain.id];
    final brand = chain.brandColor == null ? null : Color(chain.brandColor!);

    final Color plate;
    final Widget content;
    if (logo != null) {
      plate = logo.onBrandColor ? (brand ?? c.primary) : c.logoPlate;
      content = Image.asset(
        logo.asset,
        fit: BoxFit.contain,
        filterQuality: FilterQuality.medium,
        excludeFromSemantics: true,
        errorBuilder: (context, error, stack) =>
            _Name(name: chain.name, color: c.onBrandDark),
      );
    } else {
      plate = brand ?? c.primarySoft;
      content = _Name(
        name: chain.name,
        color: brand == null ? c.onPrimarySoft : c.onBrand(brand),
      );
    }

    return Semantics(
      image: true,
      label: chain.name,
      excludeSemantics: true,
      child: Container(
        height: height,
        width: width,
        padding: padding,
        decoration: BoxDecoration(
          color: plate,
          borderRadius: radius,
          border: Border.all(color: c.line, width: AppSize.hairline),
        ),
        alignment: Alignment.center,
        child: content,
      ),
    );
  }
}

/// The market name as a graphic: it stands in for a logo, so it is fitted to
/// the plate (shrinks if needed, never cut) rather than wrapped.
class _Name extends StatelessWidget {
  const _Name({required this.name, required this.color});

  final String name;
  final Color color;

  @override
  Widget build(BuildContext context) => FittedBox(
    fit: BoxFit.scaleDown,
    child: Text(
      name,
      maxLines: 1,
      textScaler: TextScaler.noScaling,
      style: AppType.chainName.copyWith(color: color),
    ),
  );
}
