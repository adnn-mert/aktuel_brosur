/// The Çarşı Pazar mark: an open brochure standing under a striped market
/// awning ("the brochure is the stall"). Drawn in code so the same shape
/// serves the splash animation, the home header and the launcher icon.
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../tokens.dart';

/// Colours of the mark. They belong to the logo, not to the UI palette, so
/// they live here next to the drawing.
@immutable
class LogoPalette {
  const LogoPalette({
    required this.awning,
    required this.awningStripe,
    required this.rail,
    required this.cover,
    required this.page,
    required this.pageShade,
    required this.pageLine,
    required this.flipTints,
  });

  /// Dark stripes and scallops of the awning.
  final Color awning;

  /// Light stripes of the awning.
  final Color awningStripe;

  /// The bar the awning hangs from.
  final Color rail;

  /// Brochure cover (seen as an edge under the pages).
  final Color cover;

  final Color page;

  /// Page colour in the fold, to give the spread some depth.
  final Color pageShade;

  /// Hints of printed lines.
  final Color pageLine;

  /// Back sides of the pages that flip during the splash: one per market
  /// brochure "passing by".
  final List<Color> flipTints;

  static const List<Color> _tints = [
    Color(0xFFE2574C),
    Color(0xFFF2B01E),
    Color(0xFF3F9E8F),
    Color(0xFFEF8A3A),
    Color(0xFF4F7FC4),
    Color(0xFFD4699B),
  ];

  /// On the paper background (light theme).
  static const LogoPalette onPaper = LogoPalette(
    awning: Color(0xFF1F5A45),
    awningStripe: Color(0xFFFFFDF9),
    rail: Color(0xFF143D2F),
    cover: Color(0xFF1F5A45),
    page: Color(0xFFFFFDF9),
    pageShade: Color(0xFFE4DBC8),
    pageLine: Color(0xFFCFC4AE),
    flipTints: _tints,
  );

  /// On the dark background (dark theme).
  static const LogoPalette onDark = LogoPalette(
    awning: Color(0xFF8AD4B0),
    awningStripe: Color(0xFFF4EEE3),
    rail: Color(0xFF5FB28C),
    cover: Color(0xFF8AD4B0),
    page: Color(0xFFF4EEE3),
    pageShade: Color(0xFFCFC5B3),
    pageLine: Color(0xFFB5AA96),
    flipTints: _tints,
  );

  /// On the green launcher-icon background.
  static const LogoPalette onGreen = LogoPalette(
    awning: Color(0xFFF2B01E),
    awningStripe: Color(0xFFFFFDF9),
    rail: Color(0xFF0E2E23),
    cover: Color(0xFF0E2E23),
    page: Color(0xFFFFFDF9),
    pageShade: Color(0xFFE4DBC8),
    pageLine: Color(0xFFCFC4AE),
    flipTints: _tints,
  );

  /// Background of the launcher icon.
  static const Color iconBackground = Color(0xFF1F5A45);

  static LogoPalette of(AppColors colors) => colors.isDark ? onDark : onPaper;
}

/// One page in the air during the splash animation.
@immutable
class PageFlip {
  const PageFlip({required this.progress, required this.tint});

  /// 0 = lying on the right, 1 = landed on the left.
  final double progress;

  /// Colour of the page's back side.
  final Color tint;
}

/// The mark, optionally with pages in mid-flip.
class LogoMark extends StatelessWidget {
  const LogoMark({
    super.key,
    required this.size,
    this.palette,
    this.flips = const [],
    this.awningReveal = 1,
  });

  final double size;

  /// Defaults to the palette that fits the active theme.
  final LogoPalette? palette;

  final List<PageFlip> flips;

  /// 0 = awning rolled up, 1 = fully out.
  final double awningReveal;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<AppColors>();
    return CustomPaint(
      size: Size.square(size),
      painter: LogoPainter(
        palette:
            palette ??
            (colors == null ? LogoPalette.onPaper : LogoPalette.of(colors)),
        flips: flips,
        awningReveal: awningReveal,
      ),
    );
  }
}

/// Paints the mark into a square. All geometry is in a 100 × 100 grid.
class LogoPainter extends CustomPainter {
  const LogoPainter({
    required this.palette,
    this.flips = const [],
    this.awningReveal = 1,
  });

  final LogoPalette palette;
  final List<PageFlip> flips;
  final double awningReveal;

  // --- Geometry (100-unit grid) -------------------------------------------
  static const double _grid = 100;

  // Awning.
  static const double _railLeft = 13;
  static const double _railRight = 87;
  static const double _railTop = 15;
  static const double _railBottom = 20.5;
  static const double _canopyTopInset = 2.5;
  static const double _canopyBottom = 37;
  static const double _canopyFlare = 4.5;
  static const int _stripes = 6;

  // Brochure.
  static const double _spineX = 50;
  static const double _spineTop = 57;
  static const double _spineLength = 28;
  static const double _pageWidth = 35;
  static const double _coverExtra = 3;
  static const double _coverDrop = 3.2;
  static const double _outerShorten = 1.5;

  /// How much a raised page climbs on screen per unit of height (the book is
  /// seen from the front, a little from above).
  static const double _lift = 0.62;

  /// Resting angle of a page lying on either side (the spread is a shallow V).
  static const double _rest = 0.22;

  /// How strongly a page bends while it is in the air.
  static const double _curl = 0.7;

  static const int _samples = 12;

  @override
  void paint(Canvas canvas, Size size) {
    final s = size.shortestSide / _grid;
    canvas.save();
    canvas.translate(
      (size.width - _grid * s) / 2,
      (size.height - _grid * s) / 2,
    );
    canvas.scale(s);

    _paintAwning(canvas);
    _paintBook(canvas);

    canvas.restore();
  }

  void _paintAwning(Canvas canvas) {
    final reveal = awningReveal.clamp(0.0, 1.0);
    final rail = Paint()..color = palette.rail;
    canvas.drawRRect(
      RRect.fromLTRBR(
        _railLeft,
        _railTop,
        _railRight,
        _railBottom,
        const Radius.circular(2.75),
      ),
      rail,
    );
    if (reveal <= 0) return;

    final top = _railBottom - 0.5;
    final bottom = top + (_canopyBottom - top) * reveal;
    final topLeft = _railLeft + _canopyTopInset;
    final topRight = _railRight - _canopyTopInset;
    final flare = _canopyFlare * reveal;
    final bottomLeft = topLeft - flare;
    final bottomRight = topRight + flare;
    final topStep = (topRight - topLeft) / _stripes;
    final bottomStep = (bottomRight - bottomLeft) / _stripes;
    final radius = bottomStep / 2;

    for (var i = 0; i < _stripes; i++) {
      final paint = Paint()
        ..color = i.isEven ? palette.awning : palette.awningStripe
        ..isAntiAlias = true;
      final t0 = topLeft + topStep * i;
      final t1 = t0 + topStep;
      final b0 = bottomLeft + bottomStep * i;
      final b1 = b0 + bottomStep;
      final path = Path()
        ..moveTo(t0, top)
        ..lineTo(t1, top)
        ..lineTo(b1, bottom)
        // Scallop: a half disc hanging under the stripe.
        ..arcToPoint(
          Offset(b0, bottom),
          radius: Radius.circular(radius),
          clockwise: true,
        )
        ..close();
      canvas.drawPath(path, paint);
    }

    // A thin outline keeps the light stripes visible on a light background.
    final outline = Paint()
      ..color = palette.awning
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.9
      ..strokeJoin = StrokeJoin.round;
    final edge = Path()
      ..moveTo(topLeft, top)
      ..lineTo(bottomLeft, bottom);
    for (var i = 0; i < _stripes; i++) {
      edge.arcToPoint(
        Offset(bottomLeft + bottomStep * (i + 1), bottom),
        radius: Radius.circular(radius),
        clockwise: false,
      );
    }
    edge
      ..lineTo(topRight, top)
      ..close();
    canvas.drawPath(edge, outline);
  }

  void _paintBook(Canvas canvas) {
    // Cover: the same spread, a little larger and lower.
    final cover = Paint()..color = palette.cover;
    for (final angle in [_rest, math.pi - _rest]) {
      canvas.drawPath(
        _sheet(angle, width: _pageWidth + _coverExtra, drop: _coverDrop),
        cover,
      );
    }
    // Spine notch so the two halves read as one bound brochure.
    canvas.drawRRect(
      RRect.fromLTRBR(
        _spineX - 2.6,
        _spineTop + 1,
        _spineX + 2.6,
        _spineTop + _spineLength + _coverDrop + 1.6,
        const Radius.circular(2.4),
      ),
      cover,
    );

    // A second leaf peeking out gives the stacks some thickness.
    final under = Paint()..color = palette.pageShade;
    for (final angle in [_rest, math.pi - _rest]) {
      canvas.drawPath(_sheet(angle, width: _pageWidth, drop: 1.5), under);
    }

    _paintRestingPage(canvas, _rest);
    _paintRestingPage(canvas, math.pi - _rest);

    // Pages in the air, the one nearest to landing on top.
    final ordered = [...flips]
      ..sort((a, b) => b.progress.compareTo(a.progress));
    for (final flip in ordered.reversed) {
      if (flip.progress <= 0 || flip.progress >= 1) continue;
      _paintFlyingPage(canvas, flip);
    }
  }

  void _paintRestingPage(Canvas canvas, double angle) {
    final path = _sheet(angle, width: _pageWidth);
    final left = angle > math.pi / 2;
    final bounds = path.getBounds();
    final paint = Paint()
      ..shader = LinearGradient(
        begin: left ? Alignment.centerRight : Alignment.centerLeft,
        end: left ? Alignment.centerLeft : Alignment.centerRight,
        colors: [palette.pageShade, palette.page, palette.page],
        stops: const [0, 0.28, 1],
      ).createShader(bounds);
    canvas.drawPath(path, paint);

    // Printed lines: two blocks per page.
    final ink = Paint()
      ..color = palette.pageLine
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.2
      ..strokeCap = StrokeCap.round;
    const rows = [0.24, 0.44, 0.64, 0.82];
    const ends = [0.86, 0.86, 0.6, 0.8];
    for (var i = 0; i < rows.length; i++) {
      final a = _point(angle, _pageWidth * 0.2, rows[i]);
      final b = _point(angle, _pageWidth * ends[i], rows[i]);
      canvas.drawLine(a, b, ink);
    }
  }

  void _paintFlyingPage(Canvas canvas, PageFlip flip) {
    final t = Curves.easeInOut.transform(flip.progress.clamp(0.0, 1.0));
    final angle = _rest + (math.pi - 2 * _rest) * t;
    final lift = math.sin(angle);
    final path = _sheet(angle, width: _pageWidth, curl: _curl * lift);
    // Before the top of the arc we see the printed front, after it the
    // coloured back. The free edge trails behind, so judge by the middle.
    final showingBack = angle - _curl * lift / 2 > math.pi / 2;
    final base = showingBack ? flip.tint : palette.page;
    final shade = Color.lerp(base, palette.rail, 0.16 * lift)!;
    canvas.drawPath(
      path,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [base, shade],
        ).createShader(path.getBounds()),
    );
    canvas.drawPath(
      path,
      Paint()
        ..color = palette.rail.withValues(alpha: 0.35)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 0.6
        ..strokeJoin = StrokeJoin.round,
    );
  }

  /// A point on a flat page at [angle]: [r] along the width from the spine,
  /// [v] from the top edge (0) to the bottom edge (1).
  Offset _point(double angle, double r, double v) {
    final x = _spineX + r * math.cos(angle);
    final rise = r * math.sin(angle) * _lift;
    final length = _spineLength - _outerShorten * (r / _pageWidth);
    return Offset(x, _spineTop - rise + length * v);
  }

  /// Outline of a page (or the cover) hinged at the spine.
  ///
  /// [curl] bends the sheet like a sail: the free edge trails behind the
  /// spine side, as paper does when it is flipped quickly.
  Path _sheet(
    double angle, {
    required double width,
    double curl = 0,
    double drop = 0,
  }) {
    final top = <Offset>[];
    final bottom = <Offset>[];
    var x = 0.0;
    var z = 0.0;
    const step = 1 / _samples;
    top.add(Offset(_spineX, _spineTop + drop));
    bottom.add(Offset(_spineX, _spineTop + _spineLength + drop));
    for (var i = 1; i <= _samples; i++) {
      final f = (i - 0.5) * step;
      final local = angle - curl * f;
      x += math.cos(local) * width * step;
      z += math.sin(local) * width * step;
      final along = i * step;
      final length = _spineLength - _outerShorten * along;
      final y = _spineTop - z * _lift + drop;
      top.add(Offset(_spineX + x, y));
      bottom.add(Offset(_spineX + x, y + length));
    }
    final path = Path()..moveTo(top.first.dx, top.first.dy);
    for (final p in top.skip(1)) {
      path.lineTo(p.dx, p.dy);
    }
    for (final p in bottom.reversed) {
      path.lineTo(p.dx, p.dy);
    }
    return path..close();
  }

  @override
  bool shouldRepaint(LogoPainter oldDelegate) =>
      oldDelegate.palette != palette ||
      oldDelegate.awningReveal != awningReveal ||
      oldDelegate.flips != flips;
}
