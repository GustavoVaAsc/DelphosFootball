/// Formatting for a player's physical and match figures: height, minutes,
/// and matches played with starts (DESIGN.md §3 "No impossible figures").
///
/// Kept together because they are the season grid's figure rules.
library;

import 'numbers.dart';

/// "1,84 m" from centimetres; "N/D" for a missing or non-positive height.
String formatHeight(num? centimetres) {
  if (centimetres == null || !centimetres.isFinite || centimetres <= 0) {
    return notAvailable;
  }
  return '${formatNumber(centimetres / 100, decimals: 2)}${nonBreakingSpace}m';
}

/// "4.285'": whole minutes with the minute mark; "N/D" without it.
String formatMinutes(num? minutes) {
  final text = formatNumber(minutes);
  return text == notAvailable ? text : "$text'";
}

/// Starts as a whole count, or `null` when unknown. Starts can never exceed
/// matches played, so a larger value is upstream noise, not a figure.
int? validStarts({required num? starts, required num? apps}) {
  if (starts == null || apps == null || !starts.isFinite || !apps.isFinite) {
    return null;
  }
  if (starts < 0 || starts > apps) return null;
  return starts.round();
}

/// "56 (45)": matches played with starts; "15 (N/D)" when starts exceed them.
String formatAppsWithStarts({required num? apps, required num? starts}) {
  final valid = validStarts(starts: starts, apps: apps);
  return '${formatNumber(apps)} (${formatNumber(valid)})';
}
