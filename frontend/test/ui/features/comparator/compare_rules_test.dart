// Tests for the comparator's season rules (DESIGN.md §4 and §2): values as
// displayed, signed deltas from the displayed values, shares in pp, tone
// only on output metrics, no delta beside N/D, and "Sin datos de
// temporada" for a player without a season row.
import 'package:delphos_frontend/data/models/player_profile_dto.dart';
import 'package:delphos_frontend/ui/features/comparator/views/compare_rules.dart';
import 'package:delphos_frontend/ui/features/comparator/views/season_figures.dart';
import 'package:delphos_frontend/ui/features/comparator/views/delta_tone.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../../support/player_fixtures.dart';

const minus = '\u2212';

SeasonFigures figures({
  int? age = 24,
  int? minutes = 4285,
  int? goals = 25,
  int? starter = 80,
  int? win = 80,
}) => (
  league: 'Bundesliga',
  age: age,
  minutes: minutes,
  goals: goals,
  assists: 32,
  starter: starter,
  win: win,
);

Map<String, SeasonRow> byLabel(List<SeasonRow> rows) => {
  for (final row in rows) row.label: row,
};

void main() {
  test('reads the displayed figures from a profile', () {
    final profile = PlayerProfileDto.fromJson(profileJson(season: seasonJson()))
        .toDomain();
    final f = seasonFigures(profile)!;
    expect(f.league, 'Bundesliga');
    expect(f.age, 24);
    expect(f.minutes, 4285);
    expect(f.starter, 80);
    expect(f.win, 80);
  });

  test('a profile without a season has no figures', () {
    final profile = PlayerProfileDto.fromJson(profileJson()).toDomain();
    expect(seasonFigures(profile), isNull);
    expect(seasonFigures(null), isNull);
  });

  test('rows come in the preview order with the reference values', () {
    final rows = seasonRows(figures(), [figures()]);
    expect(rows.map((r) => r.label), [
      'Liga',
      'Edad',
      'Minutos',
      'Goles',
      'Asistencias',
      'Titular',
      'Victorias',
    ]);
    final r = byLabel(rows);
    expect(r['Edad']!.reference, '24 años');
    expect(r['Minutos']!.reference, "4.285'");
    expect(r['Titular']!.reference, '80%');
  });

  test('output deltas are toned, age is neutral, shares are in pp', () {
    final r = byLabel(
      seasonRows(figures(), [
        figures(age: 21, minutes: 3000, goals: 30, starter: 88, win: 72),
      ]),
    );
    expect(r['Edad']!.cells.single, (
      text: '21 años',
      delta: '${minus}3',
      tone: DeltaTone.neutral,
    ));
    expect(r['Minutos']!.cells.single!.delta, "${minus}1.285'");
    expect(r['Minutos']!.cells.single!.tone, DeltaTone.down);
    expect(r['Goles']!.cells.single!.tone, DeltaTone.up);
    expect(r['Titular']!.cells.single!.delta, '+8 pp');
    expect(r['Victorias']!.cells.single!.delta, '${minus}8 pp');
    expect(r['Liga']!.cells.single!.delta, isNull);
  });

  test('an equal value shows ±0 in neutral', () {
    final r = byLabel(seasonRows(figures(), [figures()]));
    expect(r['Goles']!.cells.single, (
      text: '25',
      delta: '±0',
      tone: DeltaTone.neutral,
    ));
  });

  test('N/D on either side means no delta', () {
    final r = byLabel(seasonRows(figures(win: null), [figures(starter: null)]));
    expect(r['Titular']!.cells.single, (
      text: 'N/D',
      delta: null,
      tone: DeltaTone.neutral,
    ));
    expect(r['Victorias']!.reference, 'N/D');
    expect(r['Victorias']!.cells.single!.delta, isNull);
  });

  test('a missing season is a note, and no candidate gets a delta', () {
    final rows = byLabel(seasonRows(null, [figures(), null]));
    expect(rows['Goles']!.reference, isNull);
    expect(rows['Goles']!.cells.first!.delta, isNull);
    expect(rows['Goles']!.cells.last, isNull);
  });

  test('the price ceiling is 80% of the reference price', () {
    expect(
      priceCeilingNote(150e6),
      'Precio máximo de un reemplazo: €120,0\u00A0M',
    );
  });
}
