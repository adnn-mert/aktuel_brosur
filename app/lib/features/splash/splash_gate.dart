import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/data.dart';
import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../home/home_screen.dart';
import 'splash_screen.dart';

/// Shows the splash on top of the home screen, then fades it away.
///
/// The home screen is built underneath from the first frame, so the catalog
/// starts loading immediately: the splash never waits for data and data never
/// waits for the splash.
class SplashGate extends ConsumerStatefulWidget {
  const SplashGate({super.key, this.showSplash = true});

  final bool showSplash;

  @override
  ConsumerState<SplashGate> createState() => _SplashGateState();
}

class _SplashGateState extends ConsumerState<SplashGate> {
  late bool _splashDone = !widget.showSplash;
  late bool _splashRemoved = !widget.showSplash;

  @override
  Widget build(BuildContext context) {
    // Keep the catalog and favourites loading while the splash plays.
    ref.listen(catalogProvider, (_, _) {});
    ref.listen(favoritesProvider, (_, _) {});

    return Stack(
      fit: StackFit.expand,
      children: [
        // Not reachable by a screen reader or a stray tap until revealed.
        ExcludeSemantics(
          excluding: !_splashDone,
          child: IgnorePointer(
            ignoring: !_splashDone,
            child: const HomeScreen(),
          ),
        ),
        if (!_splashRemoved)
          IgnorePointer(
            ignoring: _splashDone,
            child: AnimatedOpacity(
              opacity: _splashDone ? 0 : 1,
              duration: context.motion(AppMotion.splashFade),
              curve: AppMotion.curve,
              onEnd: () {
                if (_splashDone) setState(() => _splashRemoved = true);
              },
              child: SplashScreen(
                onFinished: () {
                  if (!mounted) return;
                  setState(() {
                    _splashDone = true;
                    // With motion reduced the fade has no duration and
                    // `onEnd` would never fire.
                    if (context.reduceMotion) _splashRemoved = true;
                  });
                },
              ),
            ),
          ),
      ],
    );
  }
}
