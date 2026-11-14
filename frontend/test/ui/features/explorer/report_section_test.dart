// Widget tests for ReportSection: the ADR-028 rendering input, a stored
// report with its provenance, generating with the elapsed seconds and
// "Cancelar", and a generated fallback report.
import 'package:delphos_frontend/ui/features/explorer/view_models/report_view_model.dart';
import 'package:delphos_frontend/ui/features/explorer/views/report_prose.dart';
import 'package:delphos_frontend/ui/features/explorer/views/report_section.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';
import '../../../support/report_backend.dart';
import '../../../support/report_fixtures.dart';

Future<ReportViewModel> _pumpSection(
  WidgetTester tester,
  ReportsBackend backend,
) async {
  await loadArchivo();
  final vm = ReportViewModel(reports: backend.repository)..show(1000);
  addTearDown(vm.dispose);
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: SizedBox(width: 440, child: ReportSection(vm: vm)),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return vm;
}

void main() {
  testWidgets('the ADR-028 input renders only the text t', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: ReportProse(
          html:
              '<p onclick=x><img src=//evil><a href=javascript:1>t</a>'
              '<script>y</script></p>',
        ),
      ),
    );
    await tester.pumpAndSettle();
    final text = tester
        .widgetList<RichText>(find.byType(RichText))
        .map((r) => r.text.toPlainText())
        .join();
    expect(text.trim(), 't');
    expect(find.byType(Image), findsNothing);
  });

  testWidgets('a stored report shows with its provenance', (tester) async {
    final backend = ReportsBackend()
      ..stored = reportJson('llm', playerId: 1000);
    await _pumpSection(tester, backend);
    expect(find.textContaining('Texto.', findRichText: true), findsOneWidget);
    expect(
      find.textContaining('Redactado por el modelo local (qwen/qwen3.5-9b)'),
      findsOneWidget,
    );
    expect(find.text('Regenerar'), findsOneWidget);
    expect(
      find.text('El informe de scouting se genera en la siguiente versión.'),
      findsNothing,
    );
  });

  testWidgets('generating shows the seconds and can be cancelled', (
    tester,
  ) async {
    final backend = ReportsBackend();
    await _pumpSection(tester, backend);
    await tester.tap(find.text('Generar informe'));
    await tester.pump();
    expect(find.text('Generando el informe… 0 s'), findsOneWidget);
    await tester.pump(const Duration(seconds: 2));
    expect(find.text('Generando el informe… 2 s'), findsOneWidget);
    await tester.tap(find.text('Cancelar'));
    await tester.pump();
    expect(find.text('Generar informe'), findsOneWidget);
    backend.answer();
    await tester.pumpAndSettle();
    expect(find.text('Generar informe'), findsOneWidget);
  });

  testWidgets('a generated fallback report names the template', (tester) async {
    final backend = ReportsBackend();
    await _pumpSection(tester, backend);
    await tester.tap(find.text('Generar informe'));
    await tester.pump();
    backend.answer();
    await tester.pumpAndSettle();
    expect(
      find.textContaining('Plantilla determinista · generado el'),
      findsOneWidget,
    );
  });
}
