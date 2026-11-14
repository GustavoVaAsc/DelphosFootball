// Widget tests that the market table is not rebuilt from scratch by the
// dossier: opening, switching and closing keep the same table State and
// scroll offset, and a dossier-only notification rebuilds neither the table
// rows nor the filter bar. Below 1100 px the full-page dossier still replaces
// the table, so a widened window builds a fresh one (ADR-027).
import 'package:delphos_frontend/ui/features/explorer/views/dossier_panel.dart';
import 'package:delphos_frontend/ui/features/explorer/views/filter_bar.dart';
import 'package:delphos_frontend/ui/features/explorer/views/player_row.dart';
import 'package:delphos_frontend/ui/features/explorer/views/players_table.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../../support/app_harness.dart';
import '../../../support/explorer_harness.dart';

/// The table's own scroll offset; the open dossier has a scrollable too.
double tableOffset(WidgetTester tester) => tester
    .state<ScrollableState>(
      find.descendant(
        of: find.byType(PlayersTable),
        matching: find.byType(Scrollable),
      ),
    )
    .position
    .pixels;

State<PlayersTable> tableState(WidgetTester tester) =>
    tester.state<State<PlayersTable>>(find.byType(PlayersTable));

void main() {
  testWidgets('the table State and scroll offset survive open, switch, close', (
    tester,
  ) async {
    final router = await pumpAppAt(tester, '/explorador');
    await tester.drag(find.byType(ListView), const Offset(0, -600));
    await tester.pumpAndSettle();
    final state = tableState(tester);
    final offset = tableOffset(tester);
    expect(offset, greaterThan(0));
    // Two rows well inside the viewport after the drag, whatever the ids.
    final onScreen = tester
        .widgetList<PlayerRow>(find.byType(PlayerRow))
        .map((row) => row.player)
        .toList();
    final first = onScreen[2];
    final second = onScreen[3];

    await tester.tap(find.text(first.name).first);
    await tester.pumpAndSettle();
    expect(
      router.routerDelegate.currentConfiguration.uri.query,
      'jugador=${first.id}',
    );
    expect(tableState(tester), same(state));
    expect(tableOffset(tester), offset);

    await tester.tap(find.text(second.name).first);
    await tester.pumpAndSettle();
    expect(
      router.routerDelegate.currentConfiguration.uri.query,
      'jugador=${second.id}',
    );
    expect(tableState(tester), same(state));
    expect(tableOffset(tester), offset);

    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pumpAndSettle();
    expect(router.routerDelegate.currentConfiguration.uri.query, isEmpty);
    expect(tableState(tester), same(state));
    expect(tableOffset(tester), offset);
  });

  testWidgets('a dossier notification rebuilds neither rows nor filter bar', (
    tester,
  ) async {
    final backend = FakePlayersBackend();
    await pumpAppAt(tester, '/explorador', backend: backend);
    // Hold the dossier's requests, so the sections answer after the row
    // tap and each answer is a dossier-only notification.
    backend.hold = true;
    await tester.tap(find.text('Jugador 1001').first);
    await tester.pumpAndSettle();

    final rebuilt = <Type>[];
    debugOnRebuildDirtyWidget = (element, _) =>
        rebuilt.add(element.widget.runtimeType);
    // Reset in a teardown too, so a failing expect never leaks the hook
    // into the next test; the reset below stops recording before the
    // expects.
    addTearDown(() => debugOnRebuildDirtyWidget = null);
    backend.release();
    await tester.runAsync(backend.settle);
    await tester.pumpAndSettle();
    debugOnRebuildDirtyWidget = null;

    expect(find.text('Reemplazos'), findsWidgets);
    // Positive control: the dossier notifications did rebuild the panel in
    // the measured window, so the absences below are not vacuous.
    expect(rebuilt, contains(DossierPanel));
    expect(rebuilt, isNot(contains(PlayerRow)));
    expect(rebuilt, isNot(contains(PlayersTable)));
    expect(rebuilt, isNot(contains(FilterBar)));
  });

  testWidgets(
    'below 1100 px the table is dropped and a wide window rebuilds it',
    (tester) async {
      await pumpAppAt(tester, '/explorador?jugador=1000');
      final state = tableState(tester);
      addTearDown(tester.view.reset);

      tester.view.physicalSize = const Size(1000, 800);
      await tester.pumpAndSettle();
      expect(find.byType(PlayersTable), findsNothing);
      expect(find.byType(DossierPanel), findsOneWidget);

      tester.view.physicalSize = const Size(1440, 900);
      await tester.pumpAndSettle();
      expect(find.byType(PlayersTable), findsOneWidget);
      expect(find.byType(DossierPanel), findsOneWidget);
      expect(
        tester.getRect(find.byType(PlayersTable)).right,
        lessThanOrEqualTo(tester.getRect(find.byType(DossierPanel)).left),
      );
      expect(tableState(tester), isNot(same(state)));
    },
  );
}
