/// The Resumen's copy that depends on data: the provenance line under a
/// report (ADR-019 and ADR-021) and the line shown while one is generated.
///
/// Kept together as two small pure functions, tested as the section's copy.
library;

import '../../../../domain/models/scouting_report.dart';
import '../../../core/format/format.dart';
import '../../../core/labels/llm_models.dart';

/// "Redactado por PitIA (Modelo: Qwen 3.5) - Delphos Football" for a model
/// report, without the model when its id has no display name (the id itself
/// is never printed); "Plantilla determinista" for the fallback renderer.
String reportProvenance(ScoutingReport report) {
  if (!report.writtenByModel) return 'Plantilla determinista';
  final model = llmModelName(report.llmModel);
  return model == null
      ? 'Redactado por PitIA - Delphos Football'
      : 'Redactado por PitIA (Modelo: $model) - Delphos Football';
}

/// "Generando el informe… 12 s".
String generatingLine(int seconds) =>
    'Generando el informe… ${formatNumber(seconds)} s';
