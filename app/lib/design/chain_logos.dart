/// Registry of the market logos bundled with the app.
///
/// A logo is shown only to identify its market, unmodified, on a plate of the
/// colour it was drawn for. A chain that is not listed here gets a name card
/// (brand colour + big name) automatically; never draw a made-up logo.
///
/// To add one: put `assets/logos/<chain_id>.png` in place and add a line.
library;

import 'package:flutter/foundation.dart';

@immutable
class ChainLogo {
  const ChainLogo(this.asset, {this.onBrandColor = false});

  /// Asset key of the logo file.
  final String asset;

  /// True for a white logo that must sit on the market's own brand colour
  /// (Migros); false for logos drawn for a white background.
  final bool onBrandColor;
}

const String _dir = 'assets/logos';

/// Bundled logos by chain id. Sources are listed in `DESIGN.md`.
///
/// Not here on purpose: `a101` (site answers 403) and `watsons` (main site
/// blocks automated requests). Their blocks were not worked around.
const Map<String, ChainLogo> chainLogos = {
  'bim': ChainLogo('$_dir/bim.png'),
  'sok': ChainLogo('$_dir/sok.png'),
  'migros': ChainLogo('$_dir/migros.png', onBrandColor: true),
  'carrefoursa': ChainLogo('$_dir/carrefoursa.png'),
  'gratis': ChainLogo('$_dir/gratis.png'),
};
