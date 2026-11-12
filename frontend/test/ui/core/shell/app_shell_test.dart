// Widget tests for the shell: the keyboard focus ring on the sidebar, the
// browser tab title per module, and the es-ES locale.
import 'package:delphos_frontend/ui/core/theme/delphos_colors.dart';
import 'package:delphos_frontend/ui/core/widgets/focus_ring.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';

Finder visibleRing() =>
    find.byWidgetPredicate((widget) => widget is FocusRing && widget.visible);

String documentTitle(WidgetTester tester) =>
    tester.widget<Title>(find.byType(Title).last).title;

void main() {
  testWidgets('Tab focuses the first sidebar item and draws a white ring', (
    tester,
  ) async {
    await pumpAppAt(tester, '/explorador');
    expect(visibleRing(), findsNothing);

    await tester.sendKeyEvent(LogicalKeyboardKey.tab);
    await tester.pump();

    final ring = tester.widget<FocusRing>(visibleRing());
    expect(ring.color, DelphosColors.onSidebar);
    expect(
      find.descendant(
        of: visibleRing(),
        matching: find.text('Explorador de Mercado'),
      ),
      findsOneWidget,
    );

    await tester.sendKeyEvent(LogicalKeyboardKey.tab);
    await tester.pump();
    expect(
      find.descendant(
        of: visibleRing(),
        matching: find.text('Comparador Moneyball'),
      ),
      findsOneWidget,
    );
  });

  testWidgets('Enter on a focused item navigates', (tester) async {
    await pumpAppAt(tester, '/explorador');
    for (var i = 0; i < 3; i++) {
      await tester.sendKeyEvent(LogicalKeyboardKey.tab);
    }
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pumpAndSettle();
    expect(documentTitle(tester), 'Arquetipos Tácticos · DelphosFootball');
  });

  testWidgets('the not-found link shows the ink ring', (tester) async {
    await pumpAppAt(tester, '/no-existe');
    await tester.sendKeyEvent(LogicalKeyboardKey.tab);
    await tester.pump();
    expect(tester.widget<FocusRing>(visibleRing()).color, DelphosColors.ink);
  });

  const titles = {
    '/explorador': 'Explorador de Mercado · DelphosFootball',
    '/comparador/9': 'Comparador Moneyball · DelphosFootball',
    '/arquetipos': 'Arquetipos Tácticos · DelphosFootball',
    '/no-existe': 'DelphosFootball · Dirección Deportiva',
  };
  titles.forEach((path, title) {
    testWidgets('$path sets the browser tab title', (tester) async {
      await pumpAppAt(tester, path);
      expect(documentTitle(tester), title);
    });
  });

  testWidgets('the app runs in es-ES with Spanish Material strings', (
    tester,
  ) async {
    await pumpAppAt(tester, '/explorador');
    final context = tester.element(find.text('Jugador'));
    expect(Localizations.localeOf(context), const Locale('es', 'ES'));
    expect(MaterialLocalizations.of(context).closeButtonTooltip, 'Cerrar');
  });
}
