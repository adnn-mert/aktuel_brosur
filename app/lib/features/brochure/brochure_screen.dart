import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/data.dart';
import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../../design/typography.dart';
import '../../design/widgets/app_scaffold.dart';
import '../../design/widgets/feedback.dart';
import '../../l10n/app_localizations.dart';
import '../products/product_list.dart';
import 'page_viewer.dart';

/// A brochure: its pages (the viewer), its product list, or both behind two
/// big tabs when the market publishes both (BİM).
class BrochureScreen extends ConsumerStatefulWidget {
  const BrochureScreen({
    super.key,
    required this.brochureId,
    this.initialPage = 0,
  });

  final String brochureId;

  /// 0-based page to open first.
  final int initialPage;

  @override
  ConsumerState<BrochureScreen> createState() => _BrochureScreenState();
}

class _BrochureScreenState extends ConsumerState<BrochureScreen> {
  final GlobalKey<BrochurePageViewerState> _viewerKey = GlobalKey();

  /// Null until the user picks a tab; then pages are the default.
  bool? _showProducts;

  /// The product list is built only once it has been asked for, so opening
  /// a brochure to read its pages does not download the list.
  bool _productsOpened = false;

  void _select({required bool products}) {
    setState(() {
      _showProducts = products;
      if (products) _productsOpened = true;
    });
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    final brochureState = ref.watch(brochureProvider(widget.brochureId));
    final brochure = brochureState.value;

    if (brochure == null) {
      return AppScaffold(
        topBar: const AppTopBar(),
        body: brochureState.isLoading
            ? const Center(child: CircularProgressIndicator())
            : StateView(
                icon: Icons.menu_book_rounded,
                title: l10n.brochureGoneTitle,
                message: l10n.brochureGoneMessage,
              ),
      );
    }

    final chain = ref.watch(chainProvider(brochure.chainId)).value;
    final today = ref.watch(clockProvider).today();
    final dates = formatBrochureDates(brochure, today);
    final both = brochure.hasPages && brochure.hasProducts;
    final showProducts = brochure.hasPages
        ? (brochure.hasProducts && (_showProducts ?? false))
        : true;

    final Widget body;
    if (!brochure.hasPages) {
      body = ProductList(brochure: brochure);
    } else if (!brochure.hasProducts) {
      body = BrochurePageViewer(
        key: _viewerKey,
        brochure: brochure,
        initialPage: widget.initialPage,
      );
    } else {
      // Both stay alive, so switching tabs keeps the page and the scroll
      // position where they were.
      body = IndexedStack(
        index: showProducts ? 1 : 0,
        children: [
          BrochurePageViewer(
            key: _viewerKey,
            brochure: brochure,
            initialPage: widget.initialPage,
          ),
          if (_productsOpened)
            ProductList(
              brochure: brochure,
              onShowPage: (index) {
                _select(products: false);
                _viewerKey.currentState?.showPage(index);
              },
            )
          else
            const SizedBox.shrink(),
        ],
      );
    }

    return AppScaffold(
      background: showProducts ? c.paper : c.surfaceSunken,
      topBar: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          AppTopBar(
            title: chain?.name ?? brochure.title,
            subtitle: dates.isEmpty ? brochure.title : dates,
            keepOnOneRow: true,
          ),
          if (both)
            ModeTabs(
              showProducts: showProducts,
              onChanged: (products) => _select(products: products),
            ),
        ],
      ),
      body: body,
    );
  }
}

/// Two big tabs: "Broşür" | "Ürünler". Always visible on brochures that have
/// both, so the product list is never hidden behind a menu.
class ModeTabs extends StatelessWidget {
  const ModeTabs({
    super.key,
    required this.showProducts,
    required this.onChanged,
  });

  final bool showProducts;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    return DecoratedBox(
      decoration: BoxDecoration(
        color: c.paper,
        border: Border(
          bottom: BorderSide(color: c.line, width: AppSize.hairline),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpace.sm,
          vertical: AppSpace.xs,
        ),
        child: IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(
                child: _Tab(
                  key: const ValueKey('tab-brochure'),
                  label: l10n.tabBrochure,
                  icon: Icons.menu_book_rounded,
                  selected: !showProducts,
                  onTap: () => onChanged(false),
                ),
              ),
              const SizedBox(width: AppSpace.xs),
              Expanded(
                child: _Tab(
                  key: const ValueKey('tab-products'),
                  label: l10n.tabProducts,
                  icon: Icons.format_list_bulleted_rounded,
                  selected: showProducts,
                  onTap: () => onChanged(true),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Tab extends StatelessWidget {
  const _Tab({
    super.key,
    required this.label,
    required this.icon,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final foreground = selected ? c.onPrimary : c.ink;
    return Semantics(
      button: true,
      selected: selected,
      label: label,
      excludeSemantics: true,
      child: Material(
        color: selected ? c.primary : c.surface,
        shape: RoundedRectangleBorder(
          borderRadius: AppRadius.mdAll,
          side: BorderSide(
            color: selected ? c.primary : c.lineStrong,
            width: AppSize.outline,
          ),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: AppSize.touch),
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpace.sm,
                vertical: AppSpace.xs,
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // With a very large font the label needs the whole width.
                  if (!context.useStackedBars) ...[
                    Icon(icon, size: AppSize.icon, color: foreground),
                    const SizedBox(width: AppSpace.xs),
                  ],
                  Flexible(
                    child: Text(
                      label,
                      textAlign: TextAlign.center,
                      style: AppType.label.copyWith(color: foreground),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
