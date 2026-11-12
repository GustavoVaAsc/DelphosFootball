// Tests for the Resumen's copy: the provenance line for the language model
// and for the deterministic template (ADR-019), and the generating line.
import 'package:delphos_frontend/domain/models/scouting_report.dart';
import 'package:delphos_frontend/ui/features/explorer/views/report_text.dart';
import 'package:flutter_test/flutter_test.dart';

ScoutingReport report({required bool byModel, String? model}) => ScoutingReport(
  id: 1,
  playerId: 1,
  html: '<p>t</p>',
  writtenByModel: byModel,
  createdAt: DateTime.utc(2026, 11, 10, 12),
  modelRunId: 'run',
  llmModel: model,
);

void main() {
  test('a model report names the local model and the date', () {
    expect(
      reportProvenance(report(byModel: true, model: 'qwen/qwen3.5-9b')),
      'Redactado por el modelo local (qwen/qwen3.5-9b) · '
      'generado el 10 nov 2026',
    );
  });

  test('a model report without a model id omits the brackets', () {
    expect(
      reportProvenance(report(byModel: true)),
      'Redactado por el modelo local · generado el 10 nov 2026',
    );
  });

  test('the fallback report says it is the template', () {
    expect(
      reportProvenance(report(byModel: false)),
      'Plantilla determinista · generado el 10 nov 2026',
    );
  });

  test('the generating line counts whole seconds', () {
    expect(generatingLine(0), 'Generando el informe… 0 s');
    expect(generatingLine(12), 'Generando el informe… 12 s');
  });
}
