// Tests for the dossier's text rules, ported from the design preview: the
// classifier check, the valuation difference, the season grid with its
// guards, and the replacement lines.
import 'package:delphos_frontend/domain/models/player_valuation.dart';
import 'package:delphos_frontend/domain/models/replacement.dart';
import 'package:delphos_frontend/domain/models/season_stats.dart';
import 'package:delphos_frontend/domain/models/valuation_status.dart';
import 'package:delphos_frontend/ui/features/explorer/views/dossier_text.dart';
import 'package:flutter_test/flutter_test.dart';

const minus = '\u2212';
const nbsp = '\u00A0';

SeasonStats season({double starts = 45, double win = 0.8036}) => SeasonStats(
  season: 2025,
  asOfDate: DateTime(2026, 5, 27),
  leagueId: 'L1',
  minutes: 4285,
  apps: 56,
  starts: starts,
  goals: 25,
  assists: 32,
  yellowCards: 12,
  redCards: 0,
  starterRatio: 0.8,
  winRate: win,
  cleanSheetRate: 0.2857,
  goalsConcededPerMatch: 1.179,
  age: 24.5,
);

void main() {
  group('classifier check', () {
    const under = ValuationStatus.undervalued;
    const fair = ValuationStatus.fair;
    test('a missing prediction says nothing about the status', () {
      expect(
        classifierCheckLine(rf: null, dt: true, status: under),
        'Sin comprobación de los clasificadores.',
      );
    });

    test('a split between the two classifiers is stated', () {
      expect(
        classifierCheckLine(rf: true, dt: false, status: under),
        'Random Forest y árbol de decisión no coinciden.',
      );
    });

    test('agreement with the status confirms it', () {
      expect(
        classifierCheckLine(rf: true, dt: true, status: under),
        'Los dos clasificadores confirman el estado.',
      );
      expect(
        classifierCheckLine(rf: false, dt: false, status: fair),
        'Los dos clasificadores confirman el estado.',
      );
    });

    test('agreement against the status is stated neutrally', () {
      expect(
        classifierCheckLine(rf: true, dt: true, status: fair),
        'No confirman el estado: los dos clasificadores lo marcan como '
        'infravalorado.',
      );
      expect(
        classifierCheckLine(rf: false, dt: false, status: under),
        'No confirman el estado: los dos clasificadores lo marcan como '
        'no infravalorado.',
      );
    });

    test('the Random Forest probability is a guarded share', () {
      expect(rfProbabilityText(0.71), '71%');
      expect(rfProbabilityText(1.4), 'N/D');
    });
  });

  test('the difference is signed euros and a signed percentage', () {
    final v = PlayerValuation(
      playerId: 1,
      season: 2025,
      marketValueEur: 60e6,
      fairValueEur: 155.9e6,
      status: ValuationStatus.undervalued,
      rfUndervaluedProb: 0.7,
      rfUndervaluedPred: true,
      dtUndervaluedPred: true,
      modelRunId: 'r',
    );
    expect(valuationDifference(v), 'Diferencia +€95,9${nbsp}M (+160%)');
  });

  group('season grid', () {
    test('lists the eight figures in the preview order', () {
      expect(seasonMetrics(season()), [
        ('Minutos', "4.285'"),
        ('Partidos (titular)', '56 (45)'),
        ('Goles', '25'),
        ('Asistencias', '32'),
        ('Victorias', '80%'),
        ('Portería imbatida', '29%'),
        ('Goles recibidos/p', '1,18'),
        ('Tarjetas (A/R)', '12 / 0'),
      ]);
    });

    test('guards impossible starts and shares', () {
      final metrics = Map.fromEntries(
        seasonMetrics(season(starts: 60, win: 1.3))
            .map((m) => MapEntry(m.$1, m.$2)),
      );
      expect(metrics['Partidos (titular)'], '56 (N/D)');
      expect(metrics['Victorias'], 'N/D');
    });
  });

  test('replacement lines: savings, similarity and the count note', () {
    const r = Replacement(
      rank: 1,
      playerId: 2,
      name: 'C',
      position: 'Attack',
      similarity: 0.874,
      marketValueEur: 40e6,
      savingsEur: 110e6,
      costRatio: 0.2667,
      fairValueEur: 45e6,
      status: ValuationStatus.fair,
    );
    expect(replacementSavings(r), 'Ahorro €110,0${nbsp}M (${minus}73%)');
    expect(similarityText(r), '· 87% de similitud');
    expect(replacementCountNote(1), '1 de 3 reemplazos.');
    expect(replacementCountNote(0), '0 de 3 reemplazos.');
  });
}
