import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/data.dart';
import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../../design/typography.dart';
import '../../design/widgets/app_buttons.dart';
import '../../design/widgets/app_scaffold.dart';
import '../../design/widgets/chain_mark.dart';
import '../../design/widgets/feedback.dart';
import '../../l10n/app_localizations.dart';
import '../app/navigation.dart';
import 'search_field.dart';
import 'search_result_card.dart';

/// "Broşürlerde ara": type a product name, see every matching product of the
/// brochures that publish their prices as text, cheapest first.
///
/// The screen never claims more than it knows (DESIGN.md, section 15): it
/// names the markets it searches, says that the other markets' brochures are
/// pictures and are not searched, and repeats that a price is what the
/// brochure printed, for the brochure's own dates.
class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  final TextEditingController _controller = TextEditingController();
  final FocusNode _focus = FocusNode();
  String _text = '';

  @override
  void initState() {
    super.initState();
    _controller.addListener(_onTextChanged);
  }

  @override
  void dispose() {
    _controller.dispose();
    _focus.dispose();
    super.dispose();
  }

  void _onTextChanged() {
    if (_controller.text != _text) setState(() => _text = _controller.text);
  }

  /// Empties the field and brings the keyboard back.
  void _clear() {
    _controller.clear();
    _focus.requestFocus();
  }

  /// Searches for an example word. The keyboard goes away so the results
  /// are not hidden behind it.
  void _useExample(String word) {
    _controller.value = TextEditingValue(
      text: word,
      selection: TextSelection.collapsed(offset: word.length),
    );
    _focus.unfocus();
  }

  Future<void> _retry() async {
    await ref.read(catalogProvider.notifier).refresh();
    ref.invalidate(searchIndexProvider);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final index = ref.watch(searchIndexProvider);
    final offline = ref.watch(catalogProvider).value?.isStale ?? false;

    return AppScaffold(
      topBar: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // One row however large the font: with the keyboard open every dp
          // below belongs to the results.
          AppTopBar(title: l10n.searchTitle, keepOnOneRow: true),
          Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpace.screen,
              AppSpace.sm,
              AppSpace.screen,
              AppSpace.xs,
            ),
            child: ContentWidth(
              child: SearchField(
                controller: _controller,
                focusNode: _focus,
                onClear: _clear,
                onSubmitted: _focus.unfocus,
              ),
            ),
          ),
        ],
      ),
      body: index.when(
        // A quiet catalog refresh must not blank the results.
        skipLoadingOnReload: true,
        loading: () => const _Loading(),
        error: (error, _) => StateView(
          icon: Icons.wifi_off_rounded,
          title: l10n.searchErrorTitle,
          message: error is CatalogFormatException
              ? l10n.brokenMessage
              : l10n.checkConnection,
          actionLabel: l10n.retry,
          actionIcon: Icons.refresh_rounded,
          onAction: _retry,
        ),
        data: (index) => _body(context, index, offline: offline),
      ),
    );
  }

  Widget _body(
    BuildContext context,
    SearchIndex index, {
    required bool offline,
  }) {
    final l10n = AppLocalizations.of(context);

    if (index.productCount == 0) {
      // Offline, product lists that were never opened cannot be read.
      return offline
          ? StateView(
              icon: Icons.wifi_off_rounded,
              title: l10n.searchErrorTitle,
              message: l10n.searchOfflineEmptyMessage,
              actionLabel: l10n.retry,
              actionIcon: Icons.refresh_rounded,
              onAction: _retry,
            )
          : StateView(
              icon: Icons.search_off_rounded,
              title: l10n.searchEmptyIndexTitle,
              message: l10n.searchEmptyIndexMessage,
            );
    }

    final letters = normalizeForSearch(_text).replaceAll(' ', '').length;
    if (letters < AppSize.searchMinLetters) {
      return _Idle(
        index: index,
        offline: offline,
        tooShort: letters > 0,
        onExample: _useExample,
      );
    }

    final hits = index.query(_text);
    if (hits.isEmpty) {
      return _NoResults(
        query: _text.trim(),
        chains: index.chains,
        offline: offline,
        onNewSearch: _clear,
      );
    }
    return _Results(hits: hits, chains: index.chains, offline: offline);
  }
}

const EdgeInsets _listPadding = EdgeInsets.fromLTRB(
  AppSpace.screen,
  AppSpace.sm,
  AppSpace.screen,
  AppSpace.xxl,
);

/// "BİM, Migros": the searched markets as one phrase.
String _chainNames(List<Chain> chains) =>
    [for (final chain in chains) chain.name].join(', ');

class _Loading extends StatelessWidget {
  const _Loading();

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSpace.xl),
      child: Column(
        children: [
          const SizedBox.square(
            dimension: AppSize.touch,
            child: CircularProgressIndicator(strokeWidth: AppSpace.xxs),
          ),
          const SizedBox(height: AppSpace.md),
          Semantics(
            liveRegion: true,
            child: Text(
              l10n.searchLoading,
              textAlign: TextAlign.center,
              style: AppType.body.copyWith(color: c.inkSoft),
            ),
          ),
        ],
      ),
    );
  }
}

class _OfflineNotice extends StatelessWidget {
  const _OfflineNotice();

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: AppSpace.md),
    child: NoticeStrip(
      icon: Icons.wifi_off_rounded,
      text: AppLocalizations.of(context).searchOfflineNotice,
    ),
  );
}

/// Before typing: what to do, a few words to tap instead of typing, and the
/// honest scope of the search.
class _Idle extends StatelessWidget {
  const _Idle({
    required this.index,
    required this.offline,
    required this.tooShort,
    required this.onExample,
  });

  final SearchIndex index;
  final bool offline;

  /// One letter is typed: say that one more is needed.
  final bool tooShort;
  final ValueChanged<String> onExample;

  /// The example words that really find something this week; offering a
  /// word that leads to "bulunamadı" would be a small lie.
  List<String> _examples(AppLocalizations l10n) => [
    for (final word in l10n.searchExamples.split(','))
      if (index.query(word).isNotEmpty) word.trim(),
  ].take(AppSize.searchExampleCount).toList();

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    final examples = _examples(l10n);

    return ListView(
      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
      padding: _listPadding,
      children: [
        ContentWidth(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (offline) const _OfflineNotice(),
              Semantics(
                header: true,
                child: Text(
                  l10n.searchIdleTitle,
                  style: AppType.section.copyWith(color: c.ink),
                ),
              ),
              const SizedBox(height: AppSpace.xs),
              if (tooShort)
                Semantics(
                  liveRegion: true,
                  child: Text(
                    l10n.searchTooShort,
                    style: AppType.bodyStrong.copyWith(color: c.ink),
                  ),
                )
              else
                Text(
                  l10n.searchIdleMessage,
                  style: AppType.body.copyWith(color: c.inkSoft),
                ),
              if (examples.isNotEmpty) ...[
                const SizedBox(height: AppSpace.lg),
                Text(
                  l10n.searchExamplesTitle,
                  style: AppType.bodyStrong.copyWith(color: c.ink),
                ),
                const SizedBox(height: AppSpace.sm),
                Wrap(
                  spacing: AppSpace.sm,
                  runSpacing: AppSpace.sm,
                  children: [
                    for (final word in examples)
                      _ExampleChip(
                        key: ValueKey('search-example-$word'),
                        word: word,
                        onTap: () => onExample(word),
                      ),
                  ],
                ),
              ],
              const SizedBox(height: AppSpace.xl),
              Semantics(
                header: true,
                child: Text(
                  l10n.searchCoverageTitle,
                  style: AppType.title.copyWith(color: c.ink),
                ),
              ),
              const SizedBox(height: AppSpace.sm),
              Wrap(
                spacing: AppSpace.sm,
                runSpacing: AppSpace.sm,
                children: [
                  for (final chain in index.chains)
                    ChainMark(
                      key: ValueKey('search-chain-${chain.id}'),
                      chain: chain,
                      height: AppSize.resultMark,
                      width: AppSize.resultMarkWidth,
                      radius: AppRadius.smAll,
                      padding: const EdgeInsets.all(AppSpace.xs),
                    ),
                ],
              ),
              const SizedBox(height: AppSpace.sm),
              Text(
                l10n.searchCoverageNote,
                style: AppType.body.copyWith(color: c.inkSoft),
              ),
              const SizedBox(height: AppSpace.lg),
              InfoNote(text: l10n.searchPriceNote),
            ],
          ),
        ),
      ],
    );
  }
}

/// An example word as a big button (not a small chip): 56 dp tall, outlined
/// like every other "this can be pressed" control.
class _ExampleChip extends StatelessWidget {
  const _ExampleChip({super.key, required this.word, required this.onTap});

  final String word;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Semantics(
      button: true,
      label: AppLocalizations.of(context).searchExampleSpoken(word),
      excludeSemantics: true,
      child: Material(
        color: c.surface,
        shape: RoundedRectangleBorder(
          borderRadius: AppRadius.mdAll,
          side: BorderSide(color: c.lineStrong, width: AppSize.outline),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: ConstrainedBox(
            constraints: const BoxConstraints(
              minHeight: AppSize.touch,
              minWidth: AppSize.touchLarge,
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpace.lg,
                vertical: AppSpace.xs,
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Flexible(
                    child: Text(
                      word,
                      style: AppType.label.copyWith(color: c.ink),
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

class _NoResults extends StatelessWidget {
  const _NoResults({
    required this.query,
    required this.chains,
    required this.offline,
    required this.onNewSearch,
  });

  final String query;
  final List<Chain> chains;
  final bool offline;
  final VoidCallback onNewSearch;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    return ListView(
      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
      padding: _listPadding,
      children: [
        ContentWidth(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (offline) const _OfflineNotice(),
              Semantics(
                header: true,
                liveRegion: true,
                child: Text(
                  l10n.searchNoResultsTitle(query),
                  style: AppType.section.copyWith(color: c.ink),
                ),
              ),
              const SizedBox(height: AppSpace.xs),
              Text(
                l10n.searchNoResultsMessage,
                style: AppType.body.copyWith(color: c.inkSoft),
              ),
              const SizedBox(height: AppSpace.md),
              InfoNote(
                key: const ValueKey('search-coverage'),
                text: l10n.searchNoResultsCoverage(_chainNames(chains)),
              ),
              const SizedBox(height: AppSpace.xl),
              AppButton(
                label: l10n.searchNewSearch,
                icon: Icons.search_rounded,
                kind: AppButtonKind.tonal,
                expand: true,
                onPressed: onNewSearch,
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _Results extends StatelessWidget {
  const _Results({
    required this.hits,
    required this.chains,
    required this.offline,
  });

  final List<SearchHit> hits;
  final List<Chain> chains;
  final bool offline;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    // With a very large font the notes would fill the screen before the
    // first result; then the results come first and the note follows them.
    final noteFirst = !context.useStackedBars;
    return ListView.builder(
      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
      padding: _listPadding,
      itemCount: hits.length + 2,
      itemBuilder: (context, i) {
        if (i == 0) {
          return ContentWidth(
            child: Padding(
              padding: const EdgeInsets.only(bottom: AppSpace.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (offline) const _OfflineNotice(),
                  Semantics(
                    header: true,
                    liveRegion: true,
                    child: Text(
                      l10n.searchResultCount(hits.length),
                      key: const ValueKey('search-count'),
                      style: AppType.title.copyWith(color: c.ink),
                    ),
                  ),
                  const SizedBox(height: AppSpace.xxs),
                  Text(
                    l10n.searchSortNote,
                    style: AppType.body.copyWith(color: c.inkSoft),
                  ),
                  if (noteFirst) ...[
                    const SizedBox(height: AppSpace.sm),
                    InfoNote(text: l10n.searchPriceNote),
                  ],
                ],
              ),
            ),
          );
        }
        if (i == hits.length + 1) {
          return ContentWidth(
            child: Padding(
              padding: const EdgeInsets.only(top: AppSpace.sm),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (!noteFirst) ...[
                    InfoNote(text: l10n.searchPriceNote),
                    const SizedBox(height: AppSpace.md),
                  ],
                  InfoNote(
                    key: const ValueKey('search-coverage'),
                    text: l10n.searchNoResultsCoverage(_chainNames(chains)),
                  ),
                ],
              ),
            ),
          );
        }
        final hit = hits[i - 1];
        return ContentWidth(
          child: Padding(
            padding: const EdgeInsets.only(bottom: AppSpace.sm),
            child: SearchResultCard(
              key: ValueKey('search-result-${i - 1}'),
              hit: hit,
              onOpen: () => openSearchHit(context, hit),
            ),
          ),
        );
      },
    );
  }
}
