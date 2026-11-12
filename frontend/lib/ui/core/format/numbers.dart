/// es-ES number formatting: grouping, signs, percentages, shares and
/// multiples, ported from the design preview (DESIGN.md §3).
///
/// Grouping is applied by hand because es-ES leaves four-digit numbers
/// ungrouped ("5522") and the design wants "5.522". Negatives use U+2212.
/// Every helper prints "N/D" for a missing or non-finite value.
///
/// These helpers stay in one module because they are one numeric dialect:
/// percentages, shares and multiples are all built on [formatNumber].
library;

/// The minus sign used on screen (U+2212), never a hyphen.
const String minusSign = '\u2212';

/// The space between a figure and its unit ("€150,0 M", "1,84 m").
const String nonBreakingSpace = '\u00A0';

/// The text shown for a value that is missing or out of range.
const String notAvailable = 'N/D';

final RegExp _thousands = RegExp(r'\B(?=(\d{3})+(?!\d))');

bool _isFinite(num? value) => value != null && value.isFinite;

/// Formats [value] with [decimals] decimals, "." grouping and "," decimals.
String formatNumber(num? value, {int decimals = 0}) {
  if (!_isFinite(value)) return notAvailable;
  final fixed = value!.abs().toStringAsFixed(decimals);
  final [intPart, ...decimalPart] = fixed.split('.');
  final grouped = intPart.replaceAll(_thousands, '.');
  final roundsToZero = double.parse(fixed) == 0;
  final sign = value < 0 && !roundsToZero ? minusSign : '';
  return decimalPart.isEmpty
      ? '$sign$grouped'
      : '$sign$grouped,${decimalPart.single}';
}

/// Like [formatNumber] with an explicit sign; a value that rounds to zero
/// prints "±0".
String formatSignedNumber(num? value, {int decimals = 0}) {
  if (!_isFinite(value)) return notAvailable;
  if (double.parse(value!.toStringAsFixed(decimals)) == 0) return '±0';
  final text = formatNumber(value, decimals: decimals);
  return value > 0 ? '+$text' : text;
}

/// "1 jugador", "5.522 jugadores": the singular only for exactly one.
String formatCount(num count, String singular, String plural) =>
    '${formatNumber(count)} ${count == 1 ? singular : plural}';

/// Formats a ratio as a percentage. Only exactly ±1 prints ±100%: a value
/// that rounds to 100 gets one decimal, and if it still rounds to 100 it
/// prints ±99,9% below 100 and ±100,1% above it.
String formatPct(num? ratio, {int decimals = 0}) {
  if (!_isFinite(ratio)) return notAvailable;
  final pct = ratio! * 100;
  final abs = pct.abs();
  bool roundsTo100(int d) => double.parse(abs.toStringAsFixed(d)) == 100;
  if (abs == 100 || !roundsTo100(decimals)) {
    return '${formatNumber(pct, decimals: decimals)}%';
  }
  final chosen = decimals < 1 ? 1 : decimals;
  if (roundsTo100(chosen)) {
    final clamped = pct.sign * (abs < 100 ? 99.9 : 100.1);
    return '${formatNumber(clamped, decimals: 1)}%';
  }
  return '${formatNumber(pct, decimals: chosen)}%';
}

/// [formatPct] with a plus on positives that do not print as "0%".
String formatSignedPct(num? ratio) {
  final text = formatPct(ratio);
  return ratio != null && ratio > 0 && text != '0%' ? '+$text' : text;
}

/// A share (win, clean sheet, starter, classifier probability) inside 0..1,
/// or `null` when it is missing or out of range.
double? validShare(num? value) {
  if (!_isFinite(value) || value! < 0 || value > 1) return null;
  return value.toDouble();
}

/// A share as a percentage, or "N/D" when it lies outside 0..1.
String formatShare(num? value) {
  final share = validShare(value);
  return share == null ? notAvailable : formatPct(share);
}

/// A ratio such as estimate over price ("1,3x"). A positive ratio under
/// 0,05 prints "<0,1x" instead of the impossible "0,0x".
String formatMultiple(num? ratio) {
  if (!_isFinite(ratio)) return notAvailable;
  if (ratio! > 0 && ratio < 0.05) {
    return '<${formatNumber(0.1, decimals: 1)}x';
  }
  return '${formatNumber(ratio, decimals: 1)}x';
}
