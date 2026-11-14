// Widget tests for the router: the redirect from `/`, module navigation,
// player ids in the comparator path, and unknown paths (ADR-024).
import 'package:flutter_test/flutter_test.dart';

import '../support/app_harness.dart';

void main() {
  testWidgets('the root redirects to the explorer', (tester) async {
    final router = await pumpAppAt(tester, '/');
    expect(currentPath(router), '/explorador');
    expect(find.text('DelphosFootball'), findsOneWidget);
    // The title shows in the top bar and as the active nav item.
    expect(find.text('Explorador de Mercado'), findsNWidgets(2));
    expect(find.text('Jugador'), findsOneWidget);
    expect(find.text('Mostrando 1 a 50 de 5.522 jugadores'), findsOneWidget);
  });

  testWidgets('the sidebar switches modules and the title follows', (
    tester,
  ) async {
    final router = await pumpAppAt(tester, '/explorador');
    await tester.tap(find.text('Arquetipos Tácticos'));
    await tester.pumpAndSettle();
    expect(currentPath(router), '/arquetipos');
    expect(find.text('Arquetipos Tácticos'), findsNWidgets(2));
    expect(find.text('Explorador de Mercado'), findsOneWidget);
  });

  testWidgets('the comparator accepts a player id', (tester) async {
    final router = await pumpAppAt(tester, '/comparador/2147483647');
    expect(currentPath(router), '/comparador/2147483647');
    expect(find.text('Comparador Moneyball'), findsNWidgets(2));
  });

  for (final id in ['abc', '0', '2147483648', '-5', '0x1F']) {
    testWidgets('player id "$id" falls back to the bare comparator', (
      tester,
    ) async {
      final router = await pumpAppAt(tester, '/comparador/$id');
      expect(currentPath(router), '/comparador');
    });
  }

  testWidgets('an unknown path shows the not-found page', (tester) async {
    await pumpAppAt(tester, '/no-existe');
    expect(find.text('Esta dirección no existe.'), findsOneWidget);
    expect(find.text('Explorador de Mercado'), findsNothing);
    await tester.tap(find.text('Ir al Explorador de Mercado'));
    await tester.pumpAndSettle();
    expect(find.text('Jugador'), findsOneWidget);
  });
}
