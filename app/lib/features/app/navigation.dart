/// Where a tap leads. Kept in one place so the "fewest taps to reading" rule
/// (DESIGN.md, section 7) has a single home.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/data.dart';
import '../brochure/brochure_screen.dart';
import '../chain/chain_screen.dart';
import '../search/search_screen.dart';
import '../web/web_catalog_screen.dart';

/// What opening a market shows first.
enum ChainDestination { web, singleBrochure, list }

/// Decides where a market card leads:
///
/// * a web-view chain opens its own site inside the app;
/// * a chain with exactly one visible brochure opens that brochure directly
///   (there is nothing to choose, so no choosing screen);
/// * anything else opens the market screen.
({ChainDestination destination, Brochure? brochure}) chainDestination(
  Chain chain,
  BrochureGroups groups,
) {
  if (chain.isWebView) {
    return (destination: ChainDestination.web, brochure: null);
  }
  final all = [...groups.current, ...groups.upcoming, ...groups.past];
  if (all.length == 1) {
    return (destination: ChainDestination.singleBrochure, brochure: all.single);
  }
  return (destination: ChainDestination.list, brochure: null);
}

Future<void> _push(BuildContext context, Widget screen) =>
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => screen));

/// Opens [chain] from the home screen.
Future<void> openChain(BuildContext context, WidgetRef ref, Chain chain) {
  final groups =
      ref.read(brochureGroupsProvider(chain.id)).value ??
      const BrochureGroups();
  final target = chainDestination(chain, groups);
  return switch (target.destination) {
    ChainDestination.web => openChainWebsite(context, chain),
    ChainDestination.singleBrochure => openBrochure(
      context,
      target.brochure!.id,
    ),
    ChainDestination.list => _push(context, ChainScreen(chainId: chain.id)),
  };
}

/// Opens a brochure: its pages, or its product list when it has no pages.
/// [initialPage] is 0-based.
Future<void> openBrochure(
  BuildContext context,
  String brochureId, {
  int initialPage = 0,
}) => _push(
  context,
  BrochureScreen(brochureId: brochureId, initialPage: initialPage),
);

/// Opens the product search.
Future<void> openSearch(BuildContext context) =>
    _push(context, const SearchScreen());

/// The 0-based brochure page that shows the product of [hit], when the
/// brochure has pages and the product says which one; otherwise null.
int? searchHitPage(SearchHit hit) {
  final page = hit.product.pageIndex;
  final known =
      hit.brochure.hasPages && page != null && page < hit.brochure.pages.length;
  return known ? page : null;
}

/// Opens the brochure of a search result "at that product": on the page
/// that prints it when the page is known (the printed page is the best
/// proof of a price), otherwise on the product list of the brochure with
/// the product shown first.
Future<void> openSearchHit(BuildContext context, SearchHit hit) => _push(
  context,
  BrochureScreen(
    brochureId: hit.brochure.id,
    initialPage: searchHitPage(hit) ?? 0,
    focusProduct: hit.product,
  ),
);

/// Opens the chain's own brochure page inside the app.
Future<void> openChainWebsite(BuildContext context, Chain chain) =>
    _push(context, WebCatalogScreen(chainId: chain.id));
