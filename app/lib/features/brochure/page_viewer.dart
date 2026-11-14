import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/data.dart';
import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../../design/widgets/catalog_image.dart';
import 'viewer_controls.dart';
import 'zoomable_page.dart';

/// The pages of a brochure, one at a time, with the control bar below.
///
/// The one rule that keeps reading calm (DESIGN.md, section 8): while a page
/// is magnified, dragging only moves around inside that page. Pages change
/// with the arrows, or by swiping when the page is not magnified.
class BrochurePageViewer extends ConsumerStatefulWidget {
  const BrochurePageViewer({
    super.key,
    required this.brochure,
    this.initialPage = 0,
  });

  final Brochure brochure;

  /// 0-based.
  final int initialPage;

  @override
  ConsumerState<BrochurePageViewer> createState() => BrochurePageViewerState();
}

class BrochurePageViewerState extends ConsumerState<BrochurePageViewer> {
  late int _page = widget.initialPage.clamp(0, _pages.length - 1);
  late final PageController _pageController = PageController(
    initialPage: _page,
  );
  final PageZoomController _zoom = PageZoomController();

  /// Fingers currently on the page area.
  int _pointers = 0;

  /// Cancels a running offline-save loop when a newer one starts.
  int _prefetchRun = 0;
  final Set<String> _saved = {};

  List<MediaImage> get _pages => widget.brochure.pages;

  @override
  void initState() {
    super.initState();
    _zoom.addListener(_onZoomChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) => _saveForOffline());
  }

  @override
  void dispose() {
    _prefetchRun++;
    _zoom
      ..removeListener(_onZoomChanged)
      ..dispose();
    _pageController.dispose();
    super.dispose();
  }

  void _pointerGone() {
    if (_pointers > 0) setState(() => _pointers--);
  }

  void _onZoomChanged() {
    if (mounted) setState(() {});
  }

  /// Shows page [index] (0-based), e.g. from "Sayfada göster".
  void showPage(int index) {
    final target = index.clamp(0, _pages.length - 1);
    _zoom.reset();
    if (_pageController.hasClients) _pageController.jumpToPage(target);
  }

  void _turn(int delta) {
    final target = (_page + delta).clamp(0, _pages.length - 1);
    if (target == _page) return;
    // A new page always starts fitted, so it is seen whole first.
    _zoom.reset();
    if (context.reduceMotion) {
      _pageController.jumpToPage(target);
    } else {
      _pageController.animateToPage(
        target,
        duration: AppMotion.page,
        curve: AppMotion.curveInOut,
      );
    }
  }

  void _onPageChanged(int index) {
    setState(() => _page = index);
    _saveForOffline();
  }

  /// One provider object per page, so a rebuild (every finger down / up)
  /// does not look like "a different image" to the page widget.
  final Map<int, ImageProvider<Object>> _providers = {};

  ImageProvider<Object> _imageFor(int index) =>
      _providers[index] ??= _createImage(_pages[index]);

  ImageProvider<Object> _createImage(MediaImage page) {
    final w = page.width;
    final h = page.height;
    final tooLarge =
        w != null &&
        h != null &&
        (w > AppZoom.maxDecodeSide || h > AppZoom.maxDecodeSide);
    return catalogImageProvider(
      ref,
      page.url,
      decodeWidth: tooLarge ? AppZoom.maxDecodeSide : null,
      decodeHeight: tooLarge ? AppZoom.maxDecodeSide : null,
    );
  }

  /// Saves pages to the disk cache in the background so the brochure opens
  /// without internet later: the whole brochure when it is short, otherwise
  /// the next few pages from where the reader is.
  Future<void> _saveForOffline() async {
    final run = ++_prefetchRun;
    final repository = ref.read(catalogRepositoryProvider);
    final prefetch = ref.read(pagePrefetcherProvider);
    final count = _pages.length;
    final Iterable<int> wanted = count <= AppZoom.prefetchWholeLimit
        ? Iterable.generate(count, (i) => (_page + i) % count)
        : Iterable.generate(
            AppZoom.prefetchAhead,
            (i) => _page + 1 + i,
          ).where((i) => i < count);
    for (final index in wanted) {
      if (!mounted || run != _prefetchRun) return;
      final url = _pages[index].url;
      if (_saved.contains(url)) continue;
      final uri = repository.resolve(url);
      if (uri.isBundledAsset) continue;
      try {
        await prefetch(uri);
        _saved.add(url);
      } on Object {
        // Offline or the image is gone: the page shows its own retry state
        // when the reader gets there.
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final status = _zoom.value;
    // Two fingers down means "pinch", never "turn the page".
    final lockPaging = status.zoomed || _pointers > 1;

    return Column(
      children: [
        Expanded(
          child: ColoredBox(
            color: c.surfaceSunken,
            child: Listener(
              onPointerDown: (_) => setState(() => _pointers++),
              onPointerUp: (_) => _pointerGone(),
              onPointerCancel: (_) => _pointerGone(),
              child: PageView.builder(
                controller: _pageController,
                physics: lockPaging
                    ? const NeverScrollableScrollPhysics()
                    : const PageScrollPhysics(),
                itemCount: _pages.length,
                onPageChanged: _onPageChanged,
                itemBuilder: (context, index) {
                  final page = _pages[index];
                  return ZoomablePage(
                    key: ValueKey('page-$index'),
                    image: _imageFor(index),
                    pageNumber: index + 1,
                    controller: _zoom,
                    active: index == _page,
                    aspectRatio: page.aspectRatio,
                    pixelWidth: page.width,
                  );
                },
              ),
            ),
          ),
        ),
        ViewerControls(
          page: _page,
          pageCount: _pages.length,
          zoom: status,
          onPrevious: () => _turn(-1),
          onNext: () => _turn(1),
          onZoomIn: _zoom.zoomIn,
          onZoomOut: _zoom.zoomOut,
        ),
      ],
    );
  }
}
