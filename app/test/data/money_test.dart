import 'package:aktuel_brosur/data/data.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('formats kuruş the Turkish way', () {
    const cases = {
      5495: '54,95 ₺',
      124990: '1.249,90 ₺',
      0: '0,00 ₺',
      5: '0,05 ₺',
      100: '1,00 ₺',
      99999: '999,99 ₺',
      100000: '1.000,00 ₺',
      100000000: '1.000.000,00 ₺',
      -5495: '-54,95 ₺',
    };
    for (final MapEntry(:key, :value) in cases.entries) {
      expect(formatMoney(key), value, reason: '$key');
    }
  });

  test('unknown currencies fall back to the ISO code', () {
    expect(formatMoney(1200, currency: 'USD'), '12,00 USD');
    expect(formatMoney(1200, currency: 'EUR'), '12,00 €');
  });

  test('Money value type', () {
    expect(const Money(5495).format(), '54,95 ₺');
    expect(const Money(5495).toString(), '54,95 ₺');
    expect(const Money(5495), const Money(5495));
    expect(const Money(5495), isNot(const Money(5495, currency: 'EUR')));
    expect(const Money(100).compareTo(const Money(200)), lessThan(0));
  });
}
