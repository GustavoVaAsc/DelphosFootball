/// Readers for optional JSON fields, shared by every DTO's `fromJson`.
///
/// Required fields are matched with Dart 3 map patterns in each DTO; these
/// helpers cover the fields that may be `null` or absent. A present field
/// of the wrong type is a [FormatException], never a silent `null`, so a
/// contract drift fails loudly. Kept in one module because they are one
/// small parsing vocabulary.
library;

Never _wrongType(String key, Object? value, String expected) =>
    throw FormatException('Field "$key" is not $expected', value);

/// A string field that may be `null` or absent.
String? optionalString(Map<String, Object?> json, String key) =>
    switch (json[key]) {
      final String? value => value,
      final other => _wrongType(key, other, 'a string'),
    };

/// An integer field that may be `null` or absent.
int? optionalInt(Map<String, Object?> json, String key) => switch (json[key]) {
  final int? value => value,
  final other => _wrongType(key, other, 'an integer'),
};

/// A number field that may be `null` or absent, as a double.
double? optionalDouble(Map<String, Object?> json, String key) =>
    switch (json[key]) {
      final num? value => value?.toDouble(),
      final other => _wrongType(key, other, 'a number'),
    };

/// A list of objects, each parsed with [parse].
List<T> objectList<T>(
  Map<String, Object?> json,
  String key,
  T Function(Map<String, Object?>) parse,
) => switch (json[key]) {
  final List<Object?> items => [
    for (final item in items)
      switch (item) {
        final Map<String, Object?> object => parse(object),
        final other => _wrongType(key, other, 'a list of objects'),
      },
  ],
  final other => _wrongType(key, other, 'a list'),
};

/// An ISO 8601 date or date-time string, parsed.
DateTime parseIsoDate(String key, String value) =>
    DateTime.tryParse(value) ?? _wrongType(key, value, 'an ISO 8601 date');
