import 'dart:convert';
import 'dart:io';

import 'package:aktuel_brosur/data/data.dart';

/// Reference "today" of the bundled sample data.
final DateTime sampleToday = DateTime(2026, 11, 13);

/// Raw text of a file under `assets/sample/` (tests run from `app/`).
String sampleText(String path) =>
    File('assets/sample/$path').readAsStringSync();

Map<String, dynamic> sampleJson(String path) =>
    jsonDecode(sampleText(path)) as Map<String, dynamic>;

Catalog sampleCatalog() => Catalog.parse(sampleText('catalog.json'));

DateTime d(int year, int month, int day) => DateTime(year, month, day);

Chain chain(
  String id, {
  String? name,
  int sortOrder = 0,
  ChainKind kind = ChainKind.scraped,
  ChainStatus status = ChainStatus.ok,
}) => Chain(
  id: id,
  name: name ?? id,
  country: 'TR',
  kind: kind,
  webUrl: 'https://example.com/$id',
  status: status,
  lastOkAt: null,
  sortOrder: sortOrder,
);

Brochure brochure(
  String id, {
  String chainId = 'bim',
  String? title,
  DateTime? from,
  DateTime? to,
  DateTime? firstSeen,
  String? dateLabel,
}) {
  final seen = firstSeen ?? DateTime.utc(2026, 11, 1, 9);
  return Brochure(
    id: id,
    chainId: chainId,
    title: title ?? id,
    dateLabel: dateLabel,
    validFrom: from,
    validTo: to,
    kind: BrochureKind.pages,
    cover: null,
    pages: const [MediaImage(url: 'media/x/p01.webp')],
    productsUrl: null,
    productCount: 0,
    sourceUrl: 'https://example.com',
    // Midday UTC keeps the local calendar day stable in any time zone the
    // tests might run in.
    firstSeen: DateTime.utc(seen.year, seen.month, seen.day, 12),
    updatedAt: DateTime.utc(seen.year, seen.month, seen.day, 12),
  );
}
