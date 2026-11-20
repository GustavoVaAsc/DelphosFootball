// Tests for the Resumen's copy: the provenance line for the language model
// and for the deterministic template (ADR-019), and the generating line.
import 'package:delphos_frontend/domain/models/scouting_report.dart';
import 'package:delphos_frontend/ui/features/explorer/views/report_text.dart';
import 'package:flutter_test/flutter_test.dart';

ScoutingReport report({required bool byModel, String? model, String? prompt}) =>
    ScoutingReport(
      id: 1,
      playerId: 1,
      html: '<p>t</p>',
      writtenByModel: byModel,
      createdAt: DateTime.utc(2026, 11, 10, 12),
      modelRunId: 'run',
      llmModel: model,
      promptVersion: prompt,
    );

void main() {
  test('a Qwen 3.5 report is signed by PitIA with the model name', () {
    expect(
      reportProvenance(report(byModel: true, model: 'qwen/qwen3.5-9b')),
      'Redactado por PitIA (Modelo: Qwen 3.5) - Delphos Football',
    );
  });

  test('the prompt version and the date never reach the line', () {
    final line = reportProvenance(
      report(byModel: true, model: 'qwen/qwen3.5-9b', prompt: 'v1-t0.7'),
    );

    expect(line, isNot(contains('v1-t0.7')));
    expect(line, isNot(contains('2026')));
  });

  test('an unknown model is never printed', () {
    expect(
      reportProvenance(report(byModel: true, model: 'acme/foo-7b')),
      'Redactado por PitIA - Delphos Football',
    );
    expect(
      reportProvenance(report(byModel: true)),
      'Redactado por PitIA - Delphos Football',
    );
  });

  test('the fallback report says it is the template, without a date', () {
    expect(reportProvenance(report(byModel: false)), 'Plantilla determinista');
  });

  test('the generating line counts whole seconds', () {
    expect(generatingLine(0), 'Generando el informe… 0 s');
    expect(generatingLine(12), 'Generando el informe… 12 s');
  });
}
