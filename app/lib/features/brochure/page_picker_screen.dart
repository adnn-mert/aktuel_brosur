import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../../design/typography.dart';
import '../../design/widgets/app_scaffold.dart';
import '../../l10n/app_localizations.dart';

/// "Sayfa seç": every page of a long catalog as a big numbered button.
///
/// A full screen with the usual "Geri", not a sheet: nothing to drag, nothing
/// hidden. Numbers only, on purpose: the catalogs offer no small page images,
/// so thumbnails would mean downloading every full page (about 1 MB each).
/// Pops with the chosen 0-based page index, or with nothing on "Geri".
class PagePickerScreen extends StatefulWidget {
  const PagePickerScreen({
    super.key,
    required this.pageCount,
    required this.currentPage,
    this.title,
  });

  final int pageCount;

  /// 0-based.
  final int currentPage;

  /// The market's name, shown with the page count under the screen title.
  final String? title;

  @override
  State<PagePickerScreen> createState() => _PagePickerScreenState();
}

class _PagePickerScreenState extends State<PagePickerScreen> {
  final GlobalKey _currentKey = GlobalKey();

  @override
  void initState() {
    super.initState();
    // Open with the current page in view, so "where am I" is answered first.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final current = _currentKey.currentContext;
      if (current != null) {
        Scrollable.ensureVisible(current, alignment: 0.5);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final count = l10n.pageCount(widget.pageCount);
    final title = widget.title;
    final cell = context.useStackedBars
        ? AppSize.pagePickerCellLarge
        : AppSize.pagePickerCell;

    return AppScaffold(
      topBar: AppTopBar(
        title: l10n.pagePickerTitle,
        subtitle: title == null || title.isEmpty
            ? count
            : l10n.pairWithDot(title, count),
      ),
      body: LayoutBuilder(
        builder: (context, constraints) {
          const gap = AppSpace.xs;
          final width =
              math.min(constraints.maxWidth, AppSize.maxContentWidth) -
              AppSpace.screen * 2;
          final columns = math.max(1, ((width + gap) / (cell + gap)).floor());
          final side = (width - gap * (columns - 1)) / columns;
          return SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpace.screen),
            child: ContentWidth(
              child: Wrap(
                spacing: gap,
                runSpacing: gap,
                children: [
                  for (var i = 0; i < widget.pageCount; i++)
                    SizedBox.square(
                      key: i == widget.currentPage ? _currentKey : null,
                      dimension: side,
                      child: _PageButton(
                        page: i + 1,
                        current: i == widget.currentPage,
                        onTap: () => Navigator.of(context).pop(i),
                      ),
                    ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

class _PageButton extends StatelessWidget {
  const _PageButton({
    required this.page,
    required this.current,
    required this.onTap,
  });

  /// 1-based, as shown.
  final int page;
  final bool current;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    return Semantics(
      button: true,
      selected: current,
      label: current
          ? l10n.pageNumberCurrentSpoken(page)
          : l10n.pageNumberSpoken(page),
      excludeSemantics: true,
      child: Material(
        key: ValueKey('pick-page-$page'),
        color: current ? c.primary : c.surface,
        shape: RoundedRectangleBorder(
          borderRadius: AppRadius.mdAll,
          side: BorderSide(
            color: current ? c.primary : c.lineStrong,
            width: AppSize.outline,
          ),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(AppSpace.xs),
            child: FittedBox(
              fit: BoxFit.scaleDown,
              child: Text(
                MaterialLocalizations.of(context).formatDecimal(page),
                maxLines: 1,
                style: AppType.pageIndicator.copyWith(
                  color: current ? c.onPrimary : c.ink,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
