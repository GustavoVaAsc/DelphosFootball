// Widget tests for the Comparador Moneyball: the empty page, the table with
// its kickers, groups and price ceiling, the placeholder column for fewer
// candidates and for a 404, delta tones, the keyboard selector, and the
// way back to the explorer.
import 'package:delphos_frontend/ui/core/theme/delphos_colors.dart';
import 'package:delphos_frontend/ui/features/comparator/views/compare_cells.dart';
import 'package:delphos_frontend/ui/features/comparator/views/delta_tone.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';
import '../../../support/explorer_harness.dart';

String location(GoRouter router) =>
    router.routerDelegate.currentConfiguration.uri.toString();

Finder rich(String text) => find.textContaining(text, findRichText: true);

void main() {
  testWidgets('without a player there is one line and no table', (
    tester,
  ) async {
    await pumpAppAt(tester, '/comparador');
    expect(
      find.text('Elige un jugador para comparar con sus reemplazos.'),
      findsOneWidget,
    );
    expect(find.text('Valoración'), findsNothing);
    expect(find.text('Volver al Explorador de Mercado'), findsNothing);
  });

  testWidgets('the table shows the reference, three candidates and groups', (
    tester,
  ) async {
    await pumpAppAt(tester, '/comparador/7');
    expect(rich('Referencia'), findsOneWidget);
    expect(rich('· Activo élite'), findsOneWidget);
    for (final n in [1, 2, 3]) {
      expect(find.text('Reemplazo $n'), findsOneWidget);
    }
    expect(find.text('Valoración'), findsOneWidget);
    expect(find.text('Temporada 2025/26'), findsOneWidget);
    expect(
      find.text('Precio máximo de un reemplazo: €48,0\u00A0M'),
      findsOneWidget,
    );
    expect(find.text('No aplica'), findsOneWidget);
    expect(find.text('Resumen'), findsNothing);
    expect(rich('de 3 reemplazos'), findsNothing);
  });

  testWidgets('one candidate gets one placeholder column with the reason', (
    tester,
  ) async {
    final backend = FakePlayersBackend()
      ..replacementsCount = 1
      ..shortfall = 'no_peer_below_cost_ceiling';
    await pumpAppAt(tester, '/comparador/7', backend: backend);
    expect(find.text('Reemplazo 1'), findsOneWidget);
    expect(find.text('Reemplazo 2'), findsNothing);
    expect(find.text('1 de 3 reemplazos'), findsOneWidget);
    expect(
      find.text('Ningún jugador similar cuesta al menos un 20% menos.'),
      findsOneWidget,
    );
  });

  testWidgets('a replacements 404 is stated in the placeholder column', (
    tester,
  ) async {
    final backend = FakePlayersBackend()..replacementsMissing = true;
    await pumpAppAt(tester, '/comparador/7', backend: backend);
    expect(find.text('0 de 3 reemplazos'), findsOneWidget);
    expect(
      find.text('Este jugador no tiene reemplazos calculados.'),
      findsOneWidget,
    );
    expect(find.text('Valoración'), findsOneWidget);
  });

  testWidgets('deltas are toned only when the rules say so', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Column(
          children: [
            CompareCells.value((text: '30', delta: '+5', tone: DeltaTone.up)),
            CompareCells.value((
              text: '21 años',
              delta: '\u22123',
              tone: DeltaTone.neutral,
            )),
            CompareCells.value((
              text: 'N/D',
              delta: null,
              tone: DeltaTone.neutral,
            )),
          ],
        ),
      ),
    );
    Color colourOf(String text) =>
        tester.widget<Text>(find.text(text)).style!.color!;
    expect(colourOf('+5'), DelphosColors.up);
    expect(colourOf('\u22123'), DelphosColors.ink3);
    expect(find.text('N/D'), findsOneWidget);
    expect(find.byType(Text), findsNWidgets(5));
  });

  testWidgets('the selector searches, moves with the keyboard and opens', (
    tester,
  ) async {
    final router = await pumpAppAt(tester, '/comparador');
    await tester.enterText(find.byType(TextField), 'Jug');
    await tester.pump(const Duration(milliseconds: 350));
    await tester.pumpAndSettle();
    expect(find.text('Jug 501001'), findsOneWidget);
    await tester.sendKeyEvent(LogicalKeyboardKey.arrowDown);
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pumpAndSettle();
    expect(location(router), '/comparador/501001');
    expect(find.text('Reemplazo 1'), findsOneWidget);
  });

  testWidgets('"Volver" opens the reference in the explorer', (tester) async {
    final router = await pumpAppAt(tester, '/comparador/7');
    await tester.tap(find.text('Volver al Explorador de Mercado'));
    await tester.pumpAndSettle();
    expect(location(router), '/explorador?jugador=7');
  });
}
