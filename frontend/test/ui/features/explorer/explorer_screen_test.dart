// Widget tests for the Explorador de Mercado: the loading, error and empty
// states, N/D for a missing estimate, keyboard open and close of the
// dossier with focus kept on the row name, and the narrow-window dossier.
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';
import '../../../support/explorer_harness.dart';

String? focusedLabel() => FocusManager.instance.primaryFocus?.debugLabel;

Future<void> tabTo(WidgetTester tester, String label) async {
  for (var i = 0; i < 30 && focusedLabel() != label; i++) {
    await tester.sendKeyEvent(LogicalKeyboardKey.tab);
    await tester.pump();
  }
  expect(focusedLabel(), label);
}

void main() {
  testWidgets('loading shows 8 static skeleton rows and the footer line', (
    tester,
  ) async {
    final backend = FakePlayersBackend()..hold = true;
    await pumpAppAt(tester, '/explorador', backend: backend);
    expect(find.text('Cargando jugadores…'), findsOneWidget);
    expect(find.text('Jugador 1000'), findsNothing);
    backend.release();
    await tester.pumpAndSettle();
    expect(find.text('Jugador 1000'), findsOneWidget);
  });

  testWidgets('an unreachable server shows one panel and retries', (
    tester,
  ) async {
    final backend = FakePlayersBackend()..failNext = true;
    await pumpAppAt(tester, '/explorador', backend: backend);
    expect(
      find.text('No se pudo conectar con el servidor de datos'),
      findsOneWidget,
    );
    await tester.tap(find.text('Reintentar'));
    await tester.pumpAndSettle();
    expect(find.text('Jugador 1000'), findsOneWidget);
  });

  testWidgets('an empty result names the filters and resets them', (
    tester,
  ) async {
    final backend = FakePlayersBackend()..total = 0;
    await pumpAppAt(
      tester,
      '/explorador?q=zzz&estado=en-precio',
      backend: backend,
    );
    expect(find.text('Ningún jugador cumple estos filtros'), findsOneWidget);
    expect(
      find.text('Filtros activos: búsqueda «zzz» · estado En precio.'),
      findsOneWidget,
    );
    backend.total = 5522;
    await tester.tap(find.text('Restablecer filtros').last);
    await tester.pumpAndSettle();
    expect(find.text('Jugador 1000'), findsOneWidget);
  });

  testWidgets('a missing estimate prints N/D with no ratio', (tester) async {
    await pumpAppAt(tester, '/explorador');
    // The fake rows carry no fair_value_eur and no age yet.
    expect(find.text('N/D'), findsWidgets);
    expect(find.textContaining(RegExp(r'\dx$')), findsNothing);
  });

  testWidgets('Tab reaches a row name, Enter opens, Escape closes', (
    tester,
  ) async {
    final router = await pumpAppAt(tester, '/explorador');
    await tabTo(tester, 'row name 1000');
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pumpAndSettle();
    expect(
      router.routerDelegate.currentConfiguration.uri.query,
      'jugador=1000',
    );
    expect(find.text('Cerrar ficha'), findsNothing);
    expect(find.bySemanticsLabel('Cerrar ficha'), findsOneWidget);

    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pumpAndSettle();
    expect(router.routerDelegate.currentConfiguration.uri.query, isEmpty);
    expect(find.bySemanticsLabel('Cerrar ficha'), findsNothing);
    expect(focusedLabel(), 'row name 1000');
  });

  testWidgets('activating the open player again closes the dossier', (
    tester,
  ) async {
    final router = await pumpAppAt(tester, '/explorador?jugador=1001');
    expect(find.bySemanticsLabel('Cerrar ficha'), findsOneWidget);
    await tester.tap(find.text('Jugador 1001').first);
    await tester.pumpAndSettle();
    expect(router.routerDelegate.currentConfiguration.uri.query, isEmpty);
  });

  testWidgets('below 1100 px the dossier replaces the table', (tester) async {
    await pumpAppAt(tester, '/explorador?jugador=1000');
    tester.view.physicalSize = const Size(1000, 800);
    await tester.pumpAndSettle();
    expect(find.text('Jugador'), findsNothing);
    expect(find.bySemanticsLabel('Cerrar ficha'), findsOneWidget);
    expect(find.text('Mostrando 1 a 50 de 5.522 jugadores'), findsNothing);
    expect(find.byType(ListView), findsNothing);
  });
}
