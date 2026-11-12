/// Euro formatting: "€150,0 M" for millions and "€153 mil" for thousands
/// (DESIGN.md §3), with a non-breaking space before the unit.
library;

import 'numbers.dart';

/// Formats a euro amount. From 999.500 up it prints millions, so a value
/// never reads "€1.000 mil"; from 999,5 it prints thousands, so it never
/// reads "€1.000"; below that it prints plain euros.
String formatEur(num? value) {
  if (value == null || !value.isFinite) return notAvailable;
  final abs = value.abs();
  final body = switch (abs) {
    >= 999500 => '${formatNumber(abs / 1e6, decimals: 1)}${nonBreakingSpace}M',
    // From 999,5 up, plain euros would round to "€1.000".
    >= 999.5 => '${formatNumber(abs / 1e3)}${nonBreakingSpace}mil',
    _ => formatNumber(abs),
  };
  return '${value < 0 ? minusSign : ''}€$body';
}

/// [formatEur] with a plus on positive amounts.
String formatSignedEur(num? value) {
  final text = formatEur(value);
  return value != null && value > 0 ? '+$text' : text;
}
