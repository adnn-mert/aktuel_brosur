// Internal helpers for strict-but-forgiving JSON parsing. Not exported from
// `data.dart`: screens never parse JSON.

/// Thrown by [JsonReader] when a field is missing or has the wrong type.
///
/// Record-level parsers catch it and skip the record; root-level parsers turn
/// it into a `CatalogFormatException`.
class JsonFieldException implements Exception {
  const JsonFieldException(this.message);

  final String message;

  @override
  String toString() => 'JsonFieldException: $message';
}

final RegExp _dateOnly = RegExp(r'^(\d{4})-(\d{2})-(\d{2})$');

/// Typed accessors over a decoded JSON object. Unknown keys are ignored.
class JsonReader {
  JsonReader(Object? json, {this.context = 'object'})
    : map = json is Map<String, dynamic>
          ? json
          : throw JsonFieldException('$context is not a JSON object');

  final Map<String, dynamic> map;
  final String context;

  Never _bad(String key, String expected) => throw JsonFieldException(
    '$context.$key: expected $expected, got ${map[key]?.runtimeType ?? 'null'}',
  );

  bool _has(String key) => map.containsKey(key) && map[key] != null;

  String string(String key) {
    final value = map[key];
    if (value is String) return value;
    _bad(key, 'string');
  }

  String nonEmptyString(String key) {
    final value = string(key);
    if (value.trim().isEmpty) _bad(key, 'non-empty string');
    return value;
  }

  String? optString(String key) => _has(key) ? string(key) : null;

  int integer(String key) {
    final value = map[key];
    if (value is int) return value;
    // Some JSON encoders emit 5.0 for integral numbers; accept those only.
    if (value is double && value == value.truncateToDouble()) {
      return value.toInt();
    }
    _bad(key, 'integer');
  }

  int? optInteger(String key) => _has(key) ? integer(key) : null;

  List<dynamic> list(String key) {
    final value = map[key];
    if (value is List<dynamic>) return value;
    _bad(key, 'array');
  }

  Object? raw(String key) => map[key];

  /// RFC 3339 timestamp, always returned in UTC.
  DateTime dateTime(String key) {
    final parsed = DateTime.tryParse(string(key));
    if (parsed == null) _bad(key, 'RFC 3339 date-time');
    return parsed.toUtc();
  }

  DateTime? optDateTime(String key) => _has(key) ? dateTime(key) : null;

  /// `YYYY-MM-DD` calendar day, returned as a local midnight [DateTime].
  DateTime? optDate(String key) {
    if (!_has(key)) return null;
    final text = string(key);
    final match = _dateOnly.firstMatch(text);
    if (match == null) _bad(key, 'YYYY-MM-DD date');
    final year = int.parse(match.group(1)!);
    final month = int.parse(match.group(2)!);
    final day = int.parse(match.group(3)!);
    final date = DateTime(year, month, day);
    // DateTime silently rolls 2026-02-30 over to March; reject that instead.
    if (date.year != year || date.month != month || date.day != day) {
      _bad(key, 'valid calendar date');
    }
    return date;
  }
}
