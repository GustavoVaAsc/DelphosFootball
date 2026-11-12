/// The dossier's text rules, ported from the design preview
/// (`describeClassifierCheck`, the verdict gap, `seasonSectionHtml`, the
/// replacement rows). Kept together as pure functions because they are one
/// panel's copy and are tested as such; the widgets only lay them out.
library;

import '../../../../domain/models/player_valuation.dart';
import '../../../../domain/models/replacement.dart';
import '../../../../domain/models/season_stats.dart';
import '../../../../domain/models/valuation_status.dart';
import '../../../core/format/format.dart';

/// The classifier check line (DESIGN.md §4, Valuation). The status stays
/// the verdict; this line may disagree with it and says so in neutral text.
String classifierCheckLine({
  required bool? rf,
  required bool? dt,
  required ValuationStatus status,
}) {
  if (rf == null || dt == null) {
    return 'Sin comprobación de los clasificadores.';
  }
  if (rf != dt) return 'Random Forest y árbol de decisión no coinciden.';
  if (rf == (status == ValuationStatus.undervalued)) {
    return 'Los dos clasificadores confirman el estado.';
  }
  return 'No confirman el estado: los dos clasificadores lo marcan como '
      '${rf ? 'infravalorado' : 'no infravalorado'}.';
}

/// The Random Forest probability as a share ("71%"), "N/D" outside 0..1.
String rfProbabilityText(double probability) => formatShare(probability);

/// "Diferencia +€95,9 M (+160%)": the estimate minus the price.
String valuationDifference(PlayerValuation v) {
  final difference = v.fairValueEur - v.marketValueEur;
  final ratio = v.marketValueEur == 0 ? null : difference / v.marketValueEur;
  return 'Diferencia ${formatSignedEur(difference)} (${formatSignedPct(ratio)})';
}

/// The season grid's eight figures, with the starts and share guards.
List<(String, String)> seasonMetrics(SeasonStats s) => [
  ('Minutos', formatMinutes(s.minutes)),
  ('Partidos (titular)', formatAppsWithStarts(apps: s.apps, starts: s.starts)),
  ('Goles', formatNumber(s.goals)),
  ('Asistencias', formatNumber(s.assists)),
  ('Victorias', formatShare(s.winRate)),
  ('Portería imbatida', formatShare(s.cleanSheetRate)),
  ('Goles recibidos/p', formatNumber(s.goalsConcededPerMatch, decimals: 2)),
  (
    'Tarjetas (A/R)',
    '${formatNumber(s.yellowCards)} / ${formatNumber(s.redCards)}',
  ),
];

/// "Ahorro €110,0 M (−73%)": the saving, in ink, never as a verdict.
String replacementSavings(Replacement r) =>
    'Ahorro ${formatEur(r.savingsEur)} (${formatPct(r.costRatio - 1)})';

/// "· 87% de similitud", kept on one line beside the truncated club.
String similarityText(Replacement r) =>
    '· ${formatPct(r.similarity)} de similitud';

/// The bold start of the shortfall note: "1 de 3 reemplazos."
String replacementCountNote(int shown) =>
    '${formatNumber(shown)} de 3 reemplazos.';
