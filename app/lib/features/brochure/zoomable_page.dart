import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../../design/typography.dart';
import '../../design/widgets/feedback.dart';
import '../../l10n/app_localizations.dart';

/// What the + / − buttons need to know about the page on screen.
@immutable
class ZoomStatus {
  const ZoomStatus({
    this.zoomed = false,
    this.canZoomIn = false,
    this.canZoomOut = false,
  });

  /// The page is magnified (swiping pans it instead of turning pages).
  final bool zoomed;
  final bool canZoomIn;
  final bool canZoomOut;

  @override
  bool operator ==(Object other) =>
      other is ZoomStatus &&
      other.zoomed == zoomed &&
      other.canZoomIn == canZoomIn &&
      other.canZoomOut == canZoomOut;

  @override
  int get hashCode => Object.hash(zoomed, canZoomIn, canZoomOut);
}

/// Lets the viewer's buttons drive the page that is currently on screen.
/// Listeners are told only when [status] changes, not on every frame of a
/// pinch.
class PageZoomController extends ValueNotifier<ZoomStatus> {
  PageZoomController() : super(const ZoomStatus());

  ZoomablePageState? _page;

  void _attach(ZoomablePageState page) => _page = page;

  // Does not touch [value]: this can run while widgets are being built. The
  // page that becomes active reports its own status right after the frame.
  void _detach(ZoomablePageState page) {
    if (_page == page) _page = null;
  }

  void zoomIn() => _page?._zoomBy(AppZoom.step);

  void zoomOut() => _page?._zoomBy(1 / AppZoom.step);

  /// Back to the whole page. Instant unless [animate].
  void reset({bool animate = false}) => _page?._reset(animate: animate);
}

/// One brochure page that can be magnified by pinching, by double tapping
/// and through a [PageZoomController] (the + / − buttons).
///
/// Rules (DESIGN.md, section 8): at rest the page is fitted to the area and
/// cannot be dragged; once magnified it can be dragged, but only so far that
/// its edges meet the edges of the area (never into empty space).
class ZoomablePage extends StatefulWidget {
  const ZoomablePage({
    super.key,
    required this.image,
    required this.pageNumber,
    required this.controller,
    required this.active,
    this.aspectRatio,
    this.pixelWidth,
  });

  final ImageProvider<Object> image;

  /// 1-based, for the screen-reader label.
  final int pageNumber;

  final PageZoomController controller;

  /// True for the page the user is looking at; only that page listens to the
  /// controller. A page that stops being active returns to its fitted size.
  final bool active;

  /// width / height when the catalog knows it, so room is reserved before
  /// the image arrives.
  final double? aspectRatio;

  /// Image width in pixels when known, to decide how far zooming is useful.
  final int? pixelWidth;

  @override
  State<ZoomablePage> createState() => ZoomablePageState();
}

class ZoomablePageState extends State<ZoomablePage>
    with SingleTickerProviderStateMixin {
  final TransformationController _transform = TransformationController();
  late final AnimationController _animation = AnimationController(
    vsync: this,
    duration: AppMotion.zoom,
  );
  Animation<Matrix4>? _tween;

  ImageStream? _stream;
  late final ImageStreamListener _listener = ImageStreamListener(
    _onImage,
    onError: _onError,
  );
  ImageInfo? _info;
  bool _failed = false;

  Size _viewport = Size.zero;
  Size _fitted = Size.zero;
  double _maxScale = AppZoom.minMax;
  Offset? _doubleTapAt;
  bool _clamping = false;

  double get _scale => _transform.value.getMaxScaleOnAxis();

  bool get _zoomed => _scale > AppZoom.zoomedThreshold;

  @override
  void initState() {
    super.initState();
    _transform.addListener(_onTransform);
    _animation.addListener(() {
      final tween = _tween;
      if (tween != null) _transform.value = tween.value;
    });
    if (widget.active) {
      widget.controller._attach(this);
      WidgetsBinding.instance.addPostFrameCallback((_) => _report());
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _resolve();
  }

  @override
  void didUpdateWidget(ZoomablePage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.image != widget.image) {
      _failed = false;
      _resolve();
    }
    if (oldWidget.controller != widget.controller) {
      oldWidget.controller._detach(this);
    }
    if (widget.active) {
      widget.controller._attach(this);
      WidgetsBinding.instance.addPostFrameCallback((_) => _report());
    } else if (oldWidget.active) {
      widget.controller._detach(this);
      _reset(animate: false);
    }
  }

  @override
  void dispose() {
    widget.controller._detach(this);
    _stream?.removeListener(_listener);
    _info?.dispose();
    _animation.dispose();
    _transform.dispose();
    super.dispose();
  }

  // --- Image loading --------------------------------------------------------

  void _resolve() {
    final stream = widget.image.resolve(createLocalImageConfiguration(context));
    if (stream.key == _stream?.key) return;
    _stream?.removeListener(_listener);
    _stream = stream..addListener(_listener);
  }

  void _onImage(ImageInfo info, bool synchronousCall) {
    if (!mounted) {
      info.dispose();
      return;
    }
    setState(() {
      _info?.dispose();
      _info = info;
      _failed = false;
    });
    WidgetsBinding.instance.addPostFrameCallback((_) => _report());
  }

  void _onError(Object error, StackTrace? stackTrace) {
    if (mounted) setState(() => _failed = true);
  }

  void _retry() {
    _stream?.removeListener(_listener);
    _stream = null;
    setState(() => _failed = false);
    _resolve();
  }

  // --- Geometry -------------------------------------------------------------

  double get _aspectRatio {
    final info = _info;
    if (info != null && info.image.height > 0) {
      return info.image.width / info.image.height;
    }
    return widget.aspectRatio ?? AppSize.pageAspectFallback;
  }

  void _layout(Size viewport, double devicePixelRatio) {
    _viewport = viewport;
    final aspect = _aspectRatio;
    _fitted = viewport.width / viewport.height > aspect
        ? Size(viewport.height * aspect, viewport.height)
        : Size(viewport.width, viewport.width / aspect);
    final pixels = _info?.image.width ?? widget.pixelWidth;
    final screenPixels = _fitted.width * devicePixelRatio;
    final useful = pixels == null || screenPixels <= 0
        ? AppZoom.minMax
        : pixels / screenPixels * AppZoom.beyondNative;
    _maxScale = useful.clamp(AppZoom.minMax, AppZoom.maxMax).toDouble();
  }

  /// The matrix for [scale] that keeps scene point [scenePoint] under
  /// viewport point [viewportPoint], limited so the page never leaves the
  /// area.
  Matrix4 _matrixFor(double scale, Offset viewportPoint, Offset scenePoint) {
    final translation = _limit(
      scale,
      viewportPoint.dx - scenePoint.dx * scale,
      viewportPoint.dy - scenePoint.dy * scale,
    );
    return Matrix4.identity()
      ..translateByDouble(translation.dx, translation.dy, 0, 1)
      ..scaleByDouble(scale, scale, 1, 1);
  }

  /// Limits a translation: on an axis where the magnified page is smaller
  /// than the area it is centred; where it is larger its edges may not come
  /// inside the area's edges.
  Offset _limit(double scale, double tx, double ty) {
    double axis(double viewport, double fitted, double t) {
      final start = (viewport - fitted) / 2 * scale;
      final size = fitted * scale;
      if (size <= viewport) return (viewport - size) / 2 - start;
      return t.clamp(viewport - start - size, -start).toDouble();
    }

    return Offset(
      axis(_viewport.width, _fitted.width, tx),
      axis(_viewport.height, _fitted.height, ty),
    );
  }

  void _onTransform() {
    if (_clamping || _viewport.isEmpty) return;
    final m = _transform.value;
    final scale = m.getMaxScaleOnAxis();
    final t = m.getTranslation();
    final limited = _limit(scale, t.x, t.y);
    if ((limited.dx - t.x).abs() > 0.01 || (limited.dy - t.y).abs() > 0.01) {
      _clamping = true;
      _transform.value = Matrix4.identity()
        ..translateByDouble(limited.dx, limited.dy, 0, 1)
        ..scaleByDouble(scale, scale, 1, 1);
      _clamping = false;
    }
    _report();
  }

  void _report() {
    if (!mounted || !widget.active) return;
    final scale = _scale;
    final loaded = _info != null;
    widget.controller.value = ZoomStatus(
      zoomed: scale > AppZoom.zoomedThreshold,
      canZoomIn: loaded && scale < _maxScale - 0.01,
      canZoomOut: loaded && scale > AppZoom.zoomedThreshold,
    );
    // Rebuild so panning is switched on/off with the zoom state.
    if (_panWasEnabled != _zoomed) setState(() {});
  }

  bool _panWasEnabled = false;

  // --- Zoom actions ---------------------------------------------------------

  void _animateTo(Matrix4 target) {
    _animation.stop();
    if (context.reduceMotion) {
      _transform.value = target;
      return;
    }
    _tween = Matrix4Tween(
      begin: _transform.value,
      end: target,
    ).animate(CurvedAnimation(parent: _animation, curve: AppMotion.curve));
    _animation.forward(from: 0);
  }

  void _zoomAround(Offset viewportPoint, double targetScale) {
    final scale = targetScale.clamp(1.0, _maxScale).toDouble();
    final scenePoint = _transform.toScene(viewportPoint);
    _animateTo(
      scale <= AppZoom.zoomedThreshold
          ? Matrix4.identity()
          : _matrixFor(scale, viewportPoint, scenePoint),
    );
  }

  void _zoomBy(double factor) {
    if (_info == null) return;
    var target = _scale * factor;
    // Do not stop a hair above the fitted size on the way out.
    if (factor < 1 && target < AppZoom.step * 0.75) target = 1;
    _zoomAround(_viewport.center(Offset.zero), target);
  }

  void _reset({required bool animate}) {
    _animation.stop();
    if (animate) {
      _animateTo(Matrix4.identity());
    } else {
      _transform.value = Matrix4.identity();
    }
  }

  void _onDoubleTap() {
    if (_info == null) return;
    final at = _doubleTapAt ?? _viewport.center(Offset.zero);
    _zoomAround(at, _zoomed ? 1 : math.min(AppZoom.doubleTap, _maxScale));
  }

  // --- Build ----------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);

    if (_failed) {
      return StateView(
        icon: Icons.image_not_supported_rounded,
        title: l10n.pageErrorTitle,
        message: l10n.checkConnection,
        actionLabel: l10n.retry,
        actionIcon: Icons.refresh_rounded,
        onAction: _retry,
      );
    }

    return LayoutBuilder(
      builder: (context, constraints) {
        _layout(constraints.biggest, MediaQuery.devicePixelRatioOf(context));
        _panWasEnabled = _zoomed;
        final info = _info;

        final sheet = DecoratedBox(
          decoration: BoxDecoration(
            color: c.pageSheet,
            boxShadow: AppShadows.page(c),
          ),
          child: info == null
              ? _PageLoading(label: l10n.pageLoading)
              : RawImage(
                  image: info.image,
                  scale: info.scale,
                  fit: BoxFit.fill,
                  // Mip-mapped: a 2400 px page shown 1080 px wide stays
                  // crisp instead of shimmering.
                  filterQuality: FilterQuality.medium,
                ),
        );

        return Semantics(
          image: true,
          label: l10n.pageImageSpoken(widget.pageNumber),
          child: GestureDetector(
            onDoubleTapDown: (details) => _doubleTapAt = details.localPosition,
            onDoubleTap: _onDoubleTap,
            child: InteractiveViewer(
              transformationController: _transform,
              minScale: 1,
              maxScale: _maxScale,
              panEnabled: _zoomed,
              scaleEnabled: info != null,
              clipBehavior: Clip.hardEdge,
              onInteractionStart: (_) => _animation.stop(),
              child: SizedBox.fromSize(
                size: _viewport,
                child: Center(
                  child: SizedBox.fromSize(size: _fitted, child: sheet),
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

class _PageLoading extends StatelessWidget {
  const _PageLoading({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Center(
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
              label,
              textAlign: TextAlign.center,
              style: AppType.body.copyWith(color: c.inkSoft),
            ),
          ],
        ),
      ),
    );
  }
}
