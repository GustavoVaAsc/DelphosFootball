// Widget tests for the dossier's Resumen: the report text drawn from its
// stored markup, a stored report with its provenance, generating with the
// elapsed seconds and "Cancelar", the deterministic fallback, and the
// lookup failure.
import 'package:delphos_frontend/ui/features/explorer/views/report_prose.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';
import '../../../support/explorer_harness.dart';
import '../../../support/report_fixtures.dart';

void main() {
  testWidgets('the report text keeps only the words of its markup', (
    tester,
  ) async {
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
    final backend = FakePlayersBackend()
      ..storedReport = reportJson('llm', playerId: 1000);
    await pumpAppAt(tester, '/explorador?jugador=1000', backend: backend);

    expect(find.text('Resumen'), findsOneWidget);
    expect(find.textContaining('Texto.', findRichText: true), findsOneWidget);
    expect(
      find.textContaining(
        'Redactado por PitIA (Modelo: Qwen 3.5) - Delphos Football',
      ),
      findsOneWidget,
    );
    expect(find.text('Regenerar'), findsOneWidget);
    expect(find.text('Generar informe'), findsNothing);
  });

  testWidgets('without a stored report it offers Generar informe', (
    tester,
  ) async {
    await pumpAppAt(tester, '/explorador?jugador=1000');

    expect(
      find.text('Este jugador todavía no tiene informe de scouting.'),
      findsOneWidget,
    );
    expect(find.text('Generar informe'), findsOneWidget);
  });

  testWidgets('generating shows the seconds and can be cancelled', (
    tester,
  ) async {
    final backend = FakePlayersBackend();
    await pumpAppAt(tester, '/explorador?jugador=1000', backend: backend);
    backend.hold = true;
    await tester.ensureVisible(find.text('Generar informe'));
    await tester.tap(find.text('Generar informe'));
    await tester.pump();
    expect(find.text('Generando el informe… 0 s'), findsOneWidget);
    await tester.pump(const Duration(seconds: 2));
    expect(find.text('Generando el informe… 2 s'), findsOneWidget);
    // The rest of the dossier stays on screen.
    expect(find.text('Precio de mercado'), findsOneWidget);
    await tester.tap(find.text('Cancelar'));
    await tester.pump();
    expect(find.text('Generar informe'), findsOneWidget);
    backend.release();
    await tester.pumpAndSettle();
    expect(find.text('Generar informe'), findsOneWidget);
  });

  testWidgets('a generated fallback report names the template', (tester) async {
    await pumpAppAt(tester, '/explorador?jugador=1000');
    await tester.ensureVisible(find.text('Generar informe'));
    await tester.tap(find.text('Generar informe'));
    await tester.pumpAndSettle();

    expect(find.text('Plantilla determinista'), findsOneWidget);
    expect(find.textContaining('qwen'), findsNothing);
  });

  testWidgets('a generated model report names the model', (tester) async {
    final backend = FakePlayersBackend()..reportFromModel = true;
    await pumpAppAt(tester, '/explorador?jugador=1000', backend: backend);
    await tester.ensureVisible(find.text('Generar informe'));
    await tester.tap(find.text('Generar informe'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Redactado por PitIA'), findsOneWidget);
  });

  testWidgets('a failed lookup is one sentence with Reintentar', (
    tester,
  ) async {
    final backend = FakePlayersBackend()..failReports = true;
    await pumpAppAt(tester, '/explorador?jugador=1000', backend: backend);

    expect(find.text('No se pudo cargar el informe.'), findsOneWidget);
    // The other sections are untouched.
    expect(find.text('Precio de mercado'), findsOneWidget);

    backend.failReports = false;
    await tester.ensureVisible(find.text('Reintentar'));
    await tester.tap(find.text('Reintentar'));
    await tester.pumpAndSettle();

    expect(find.text('Generar informe'), findsOneWidget);
  });
}
