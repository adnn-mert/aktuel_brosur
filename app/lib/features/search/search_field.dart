import 'package:flutter/material.dart';

import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../../design/typography.dart';
import '../../design/widgets/app_buttons.dart';
import '../../design/widgets/app_scaffold.dart';
import '../../l10n/app_localizations.dart';

/// The search box: large letters, a thick frame that turns to the action
/// colour while the keyboard is on it, and a 56 dp "Yazıyı sil" button that
/// appears as soon as there is something to delete.
class SearchField extends StatefulWidget {
  const SearchField({
    super.key,
    required this.controller,
    required this.focusNode,
    required this.onClear,
    this.onSubmitted,
    this.autofocus = true,
  });

  final TextEditingController controller;
  final FocusNode focusNode;

  /// Called by the clear button (the screen empties the text and brings the
  /// keyboard back).
  final VoidCallback onClear;

  /// Called when the keyboard's own "Ara" key is pressed.
  final VoidCallback? onSubmitted;

  final bool autofocus;

  @override
  State<SearchField> createState() => _SearchFieldState();
}

class _SearchFieldState extends State<SearchField> {
  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_changed);
    widget.focusNode.addListener(_changed);
  }

  @override
  void didUpdateWidget(SearchField oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.controller != widget.controller) {
      oldWidget.controller.removeListener(_changed);
      widget.controller.addListener(_changed);
    }
    if (oldWidget.focusNode != widget.focusNode) {
      oldWidget.focusNode.removeListener(_changed);
      widget.focusNode.addListener(_changed);
    }
  }

  @override
  void dispose() {
    widget.controller.removeListener(_changed);
    widget.focusNode.removeListener(_changed);
    super.dispose();
  }

  void _changed() {
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    final focused = widget.focusNode.hasFocus;
    final hasText = widget.controller.text.isNotEmpty;
    final textStyle = AppType.title.copyWith(color: c.ink);

    return DecoratedBox(
      // Drawn over the box so a thicker frame never moves the text.
      position: DecorationPosition.foreground,
      decoration: BoxDecoration(
        borderRadius: AppRadius.mdAll,
        border: Border.all(
          color: focused ? c.primary : c.lineStrong,
          width: focused ? AppSize.focusRing : AppSize.outline,
        ),
      ),
      child: Material(
        color: c.surface,
        borderRadius: AppRadius.mdAll,
        clipBehavior: Clip.antiAlias,
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: AppSize.touchLarge),
          child: Row(
            children: [
              // With a very large font the letters need the whole width.
              if (!context.useStackedBars)
                Padding(
                  padding: const EdgeInsets.only(left: AppSpace.sm),
                  child: ExcludeSemantics(
                    child: Icon(
                      Icons.search_rounded,
                      size: AppSize.icon,
                      color: c.inkSoft,
                    ),
                  ),
                ),
              Expanded(
                child: Semantics(
                  label: l10n.searchFieldSpoken,
                  child: TextField(
                    key: const ValueKey('search-input'),
                    controller: widget.controller,
                    focusNode: widget.focusNode,
                    autofocus: widget.autofocus,
                    style: textStyle,
                    cursorColor: c.primary,
                    cursorWidth: AppSize.focusRing,
                    keyboardType: TextInputType.text,
                    textInputAction: TextInputAction.search,
                    textCapitalization: TextCapitalization.none,
                    autocorrect: false,
                    onSubmitted: (_) => widget.onSubmitted?.call(),
                    decoration: InputDecoration(
                      border: InputBorder.none,
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: AppSpace.sm,
                        vertical: AppSpace.sm,
                      ),
                      hintText: l10n.searchFieldHint,
                      hintMaxLines: 2,
                      hintStyle: textStyle.copyWith(
                        color: c.inkSoft,
                        fontWeight: FontWeight.w400,
                      ),
                    ),
                  ),
                ),
              ),
              if (hasText)
                Padding(
                  padding: const EdgeInsets.all(AppSpace.xxs),
                  child: AppIconButton(
                    key: const ValueKey('search-clear'),
                    icon: Icons.close_rounded,
                    label: l10n.searchClear,
                    onPressed: widget.onClear,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
