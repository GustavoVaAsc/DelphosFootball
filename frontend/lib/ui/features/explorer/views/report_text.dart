/// The Resumen's copy that depends on data: the provenance line under a
/// report (ADR-019 and ADR-021) and the line shown while one is generated.
///
/// Kept together as two small pure functions, tested as the section's copy.
library;

import '../../../../domain/models/scouting_report.dart';
import '../../../core/format/format.dart';

/// "Redactado por el modelo local (qwen/qwen3.5-9b) · generado el 10 nov
/// 2026", or "Plantilla determinista · …" for the fallback renderer. The
/// date is the reader's local date.
String reportProvenance(ScoutingReport report) {
  final model = report.llmModel;
  final author = !report.writtenByModel
      ? 'Plantilla determinista'
      : model == null
      ? 'Redactado por el modelo local'
      : 'Redactado por el modelo local ($model)';
  return '$author · generado el ${formatDate(report.createdAt)}';
}

/// "Generando el informe… 12 s".
String generatingLine(int seconds) =>
    'Generando el informe… ${formatNumber(seconds)} s';
