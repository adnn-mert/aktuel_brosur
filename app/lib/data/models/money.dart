/// An amount of money in minor units (kuruş for TRY).
///
/// Prices travel as integers end to end so that no floating point rounding
/// can ever change a printed price.
class Money implements Comparable<Money> {
  const Money(this.minor, {this.currency = 'TRY'});

  /// Amount in minor units: 5495 means 54,95 ₺.
  final int minor;

  /// ISO 4217 code, e.g. `TRY`.
  final String currency;

  /// Turkish display form, e.g. `54,95 ₺`, `1.249,90 ₺`.
  String format() => formatMoney(minor, currency: currency);

  @override
  int compareTo(Money other) => minor.compareTo(other.minor);

  @override
  bool operator ==(Object other) =>
      other is Money && other.minor == minor && other.currency == currency;

  @override
  int get hashCode => Object.hash(minor, currency);

  @override
  String toString() => format();
}

const Map<String, String> _currencySymbols = {'TRY': '₺', 'EUR': '€'};

/// Formats [minor] units the Turkish way: `.` groups thousands, `,` separates
/// kuruş, and the symbol follows the number after a space.
///
/// `formatMoney(5495) == '54,95 ₺'`, `formatMoney(124990) == '1.249,90 ₺'`.
/// Unknown currencies fall back to their ISO code (`12,00 USD`).
String formatMoney(int minor, {String currency = 'TRY'}) {
  final negative = minor < 0;
  final absolute = minor.abs();
  final whole = (absolute ~/ 100).toString();
  final fraction = (absolute % 100).toString().padLeft(2, '0');

  final grouped = StringBuffer();
  for (var i = 0; i < whole.length; i++) {
    final remaining = whole.length - i;
    if (i > 0 && remaining % 3 == 0) grouped.write('.');
    grouped.write(whole[i]);
  }

  final symbol = _currencySymbols[currency] ?? currency;
  return '${negative ? '-' : ''}$grouped,$fraction $symbol';
}
