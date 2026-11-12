/// The comparator's season rules, ported from the design preview's
/// `renderMoneyballExpandedView` (DESIGN.md §4 and §2):
/// - values are rounded as displayed, and deltas are computed from the
///   displayed values, so the arithmetic on screen adds up;
/// - shares are whole percentage points and their deltas are in "pp";
/// - only output metrics are toned (minutes, goals, assists, starter and
///   win shares); age and league are neutral;
/// - a value that prints "N/D", on either side, has no delta;
/// - a player without a season row gets "Sin datos de temporada" (`null`).
///
/// The figures themselves come from `season_figures.dart`.
///
/// Kept together as pure functions: they are one table's rules and are
/// tested as such.
library;

import '../../../core/format/format.dart';
import 'delta_tone.dart';
import 'season_figures.dart';

/// One candidate cell: the value, its signed delta, and the delta's tone.
typedef CompareCell = ({String text, String? delta, DeltaTone tone});

/// One metric row: the reference text (`null` for no season data) and one
/// cell per candidate (`null` for a candidate without season data).
typedef SeasonRow = ({
  String label,
  String? reference,
  List<CompareCell?> cells,
});

/// The seven season rows for [reference] against each of [candidates].
List<SeasonRow> seasonRows(
  SeasonFigures? reference,
  List<SeasonFigures?> candidates,
) {
  SeasonRow row(
    String label,
    int? Function(SeasonFigures f) pick,
    String Function(int value) format,
    String Function(int diff) formatDiff, {
    required bool toned,
  }) {
    final ref = reference == null ? null : pick(reference);
    String show(int? value) => value == null ? notAvailable : format(value);
    return (
      label: label,
      reference: reference == null ? null : show(ref),
      cells: [
        for (final candidate in candidates)
          candidate == null
              ? null
              : _cell(pick(candidate), ref, show, formatDiff, toned: toned),
      ],
    );
  }

  String points(int value) => '${formatNumber(value)}%';
  String pp(int diff) => '${formatSignedNumber(diff)} pp';
  return [
    (
      label: 'Liga',
      reference: reference == null ? null : reference.league ?? notAvailable,
      cells: [
        for (final c in candidates)
          c == null
              ? null
              : (
                  text: c.league ?? notAvailable,
                  delta: null,
                  tone: DeltaTone.neutral,
                ),
      ],
    ),
    row(
      'Edad',
      (f) => f.age,
      (v) => formatCount(v, 'año', 'años'),
      formatSignedNumber,
      toned: false,
    ),
    row(
      'Minutos',
      (f) => f.minutes,
      formatMinutes,
      (d) => "${formatSignedNumber(d)}'",
      toned: true,
    ),
    row('Goles', (f) => f.goals, formatNumber, formatSignedNumber, toned: true),
    row(
      'Asistencias',
      (f) => f.assists,
      formatNumber,
      formatSignedNumber,
      toned: true,
    ),
    row('Titular', (f) => f.starter, points, pp, toned: true),
    row('Victorias', (f) => f.win, points, pp, toned: true),
  ];
}

CompareCell _cell(
  int? value,
  int? reference,
  String Function(int? value) show,
  String Function(int diff) formatDiff, {
  required bool toned,
}) {
  if (value == null || reference == null) {
    return (text: show(value), delta: null, tone: DeltaTone.neutral);
  }
  final diff = value - reference;
  final tone = !toned || diff == 0
      ? DeltaTone.neutral
      : (diff > 0 ? DeltaTone.up : DeltaTone.down);
  return (text: show(value), delta: formatDiff(diff), tone: tone);
}

/// The reference cell of the savings row: the most a replacement may cost
/// (80% of the reference's price).
String priceCeilingNote(double referencePrice) =>
    'Precio máximo de un reemplazo: ${formatEur(referencePrice * 0.8)}';
