import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../../design/typography.dart';
import '../../design/widgets/logo_mark.dart';
import '../../l10n/app_localizations.dart';

/// Opening screen: the awning rolls out, the brochure's pages flip quickly
/// from right to left (each with a different coloured back, like the markets'
/// brochures passing by), then the name appears.
///
/// With "reduce motion" on, a still logo and the name are shown briefly.
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key, required this.onFinished});

  final VoidCallback onFinished;

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

/// Timeline of the splash, as fractions of [AppMotion.splash].
abstract final class _Timeline {
  static const Interval logoIn = Interval(0, 0.14, curve: Curves.easeOut);
  static const Interval awning = Interval(
    0.02,
    0.24,
    curve: Curves.easeOutBack,
  );
  static const double flipStart = 0.16;
  static const double flipStagger = 0.075;
  static const double flipLength = 0.27;
  static const Interval name = Interval(0.64, 0.84, curve: Curves.easeOut);
  static const Interval tagline = Interval(0.74, 0.94, curve: Curves.easeOut);

  static const double logoStartScale = 0.9;
  static const double textRise = 12;
}

class _SplashScreenState extends State<SplashScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: AppMotion.splash,
  );
  Timer? _stillTimer;
  bool _started = false;
  bool _finished = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;
    if (context.reduceMotion) {
      _controller.value = 1;
      _stillTimer = Timer(AppMotion.splashStill, _finish);
    } else {
      _startWhenVisible();
    }
  }

  /// Starts the animation once the first frame is really on screen. On a
  /// cold start the system splash covers the app until then; starting
  /// earlier would play the page flip where nobody can see it.
  Future<void> _startWhenVisible() async {
    final binding = WidgetsBinding.instance;
    if (!binding.firstFrameRasterized) {
      await Future.any<void>([
        binding.waitUntilFirstFrameRasterized,
        Future<void>.delayed(AppMotion.splashStartLimit),
      ]);
    }
    if (!mounted) return;
    await _controller.forward();
    _finish();
  }

  void _finish() {
    if (_finished || !mounted) return;
    _finished = true;
    widget.onFinished();
  }

  @override
  void dispose() {
    _stillTimer?.cancel();
    _controller.dispose();
    super.dispose();
  }

  List<PageFlip> _flips(double t, LogoPalette palette) {
    final flips = <PageFlip>[];
    for (var i = 0; i < palette.flipTints.length; i++) {
      final start = _Timeline.flipStart + _Timeline.flipStagger * i;
      final progress = ((t - start) / _Timeline.flipLength).clamp(0.0, 1.0);
      if (progress > 0 && progress < 1) {
        flips.add(PageFlip(progress: progress, tint: palette.flipTints[i]));
      }
    }
    return flips;
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    final palette = LogoPalette.of(c);

    return Material(
      color: c.paper,
      child: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpace.xl),
            child: AnimatedBuilder(
              animation: _controller,
              builder: (context, _) {
                final t = _controller.value;
                final logoIn = _Timeline.logoIn.transform(t);
                final name = _Timeline.name.transform(t);
                final tagline = _Timeline.tagline.transform(t);
                return Semantics(
                  label: l10n.appTitle,
                  excludeSemantics: true,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Opacity(
                        opacity: logoIn,
                        child: Transform.scale(
                          scale:
                              _Timeline.logoStartScale +
                              (1 - _Timeline.logoStartScale) * logoIn,
                          child: LogoMark(
                            size: AppSize.splashLogo,
                            palette: palette,
                            awningReveal: _Timeline.awning.transform(t),
                            flips: _flips(t, palette),
                          ),
                        ),
                      ),
                      const SizedBox(height: AppSpace.md),
                      _Rising(
                        progress: name,
                        child: Text(
                          l10n.appTitle,
                          textAlign: TextAlign.center,
                          style: AppType.wordmark.copyWith(color: c.ink),
                        ),
                      ),
                      const SizedBox(height: AppSpace.xs),
                      _Rising(
                        progress: tagline,
                        child: Text(
                          l10n.appTagline,
                          textAlign: TextAlign.center,
                          style: AppType.body.copyWith(color: c.inkSoft),
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        ),
      ),
    );
  }
}

/// Fades in while rising a few pixels.
class _Rising extends StatelessWidget {
  const _Rising({required this.progress, required this.child});

  final double progress;
  final Widget child;

  @override
  Widget build(BuildContext context) => Opacity(
    opacity: progress,
    child: Transform.translate(
      offset: Offset(0, _Timeline.textRise * (1 - progress)),
      child: child,
    ),
  );
}
