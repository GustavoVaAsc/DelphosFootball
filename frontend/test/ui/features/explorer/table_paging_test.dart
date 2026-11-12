// Widget tests for the table's pager: Anterior is disabled on page 1,
// Siguiente moves the URL to page 2 and the list back to its top row.
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';

void main() {
  testWidgets('Siguiente goes to page 2 and scrolls to the top', (
    tester,
  ) async {
    final router = await pumpAppAt(tester, '/explorador');
    await tester.drag(find.byType(ListView), const Offset(0, -600));
    await tester.pumpAndSettle();
    expect(
      tester
          .state<ScrollableState>(find.byType(Scrollable).last)
          .position
          .pixels,
      greaterThan(0),
    );

    await tester.tap(find.text('Anterior'));
    await tester.pumpAndSettle();
    expect(router.routerDelegate.currentConfiguration.uri.query, isEmpty);

    await tester.tap(find.text('Siguiente'));
    await tester.pumpAndSettle();
    expect(router.routerDelegate.currentConfiguration.uri.query, 'pagina=2');
    expect(find.text('Mostrando 51 a 100 de 5.522 jugadores'), findsOneWidget);
    expect(find.text('Jugador 2000'), findsOneWidget);
    expect(
      tester
          .state<ScrollableState>(find.byType(Scrollable).last)
          .position
          .pixels,
      0,
    );
  });
}
