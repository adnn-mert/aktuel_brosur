/// Registry of the market logos bundled with the app.
///
/// A logo is shown only to identify its market, unmodified, on a plate of the
/// colour it was drawn for. A chain that is not listed here gets a name card
/// (brand colour + big name) automatically; never draw a made-up logo.
///
/// To add one: put `assets/logos/<chain_id>.png` in place and add a line.
library;

import 'package:flutter/foundation.dart';
import 'package:flutter/painting.dart' show Color;

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

/// Name-card colours for chains the catalog gives no `brand_color` for.
///
/// Used only when the chain has no logo file and the catalog has no colour
/// (a colour in the catalog always wins). Each is a flat background close to
/// the dominant colour of the market's own brochures and shop signs; none is
/// claimed to be an official brand value and none is artwork. The name on
/// top picks black or white by contrast (`AppColors.onBrand`), so every
/// entry stays at 4.5:1 or better (tested).
///
/// The two reds differ in warmth on purpose, but what tells two markets
/// apart is the name written large, never the colour alone.
const Map<String, Color> chainPlateColors = {
  'hakmar': Color(0xFFD62B1F), // warm red
  'bonveno': Color(0xFFB5175E), // raspberry
  'metro': Color(0xFF003B7E), // navy
  'rossmann': Color(0xFFB00030), // deep crimson
  'tkkoop': Color(0xFF00843D), // green
};
