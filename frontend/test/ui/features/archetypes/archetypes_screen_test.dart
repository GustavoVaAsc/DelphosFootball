// Widget tests for the Arquetipos Tácticos view: the intro sentence from
// the data, share bar proportions and legend, the cards' copy and aligned
// rows on one card surface, the representative player links and "Ver en el
// explorador".
import 'package:delphos_frontend/ui/features/archetypes/views/archetype_grid.dart';
import 'package:delphos_frontend/ui/features/archetypes/views/archetype_pitch.dart';
import 'package:delphos_frontend/ui/features/archetypes/views/share_bar.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';
import '../../../support/explorer_harness.dart';

String location(GoRouter router) =>
    router.routerDelegate.currentConfiguration.uri.toString();

void main() {
  testWidgets('the intro states the total and the shares', (tester) async {
    await pumpAppAt(tester, '/arquetipos');
    expect(
      find.text(
        'Clasificación de los 5.522 jugadores de campo europeos en tres '
        'perfiles según su producción estadística por 90 minutos.',
      ),
      findsOneWidget,
    );
    expect(
      find.text('Reparto de los 5.522 jugadores por arquetipo'),
      findsOneWidget,
    );
    for (final legend in ['1.219 · 22%', '503 · 9%', '3.800 · 69%']) {
      expect(find.text(legend), findsOneWidget);
    }
  });

  testWidgets('bar segments are sized by player count', (tester) async {
    await pumpAppAt(tester, '/arquetipos');
    final segments = tester
        .widgetList<Expanded>(
          find.descendant(
            of: find.byType(ShareBar),
            matching: find.byType(Expanded),
          ),
        )
        .map((e) => e.flex)
        .toList();
    // Three bar segments, then three legend items with the same flex.
    expect(segments, [1219, 503, 3800, 1219, 503, 3800]);
  });

  testWidgets('each bar segment is 12 px tall and sized by count', (
    tester,
  ) async {
    await pumpAppAt(tester, '/arquetipos');
    final sizes = [
      for (final id in [0, 1, 2])
        tester.getSize(find.byKey(ShareBar.segmentKey(id))),
    ];
    for (final size in sizes) {
      expect(size.height, 12);
    }
    final counts = [1219, 503, 3800];
    for (var i = 1; i < 3; i++) {
      final expected = sizes[0].width * counts[i] / counts[0];
      expect(sizes[i].width, closeTo(expected, 1));
    }
  });

  testWidgets('each card is one surface behind all its rows', (tester) async {
    await pumpAppAt(tester, '/arquetipos');
    final card = tester.getRect(find.byKey(ArchetypeGrid.cardKey(0)));
    final top = tester.getRect(find.text('1.219 jugadores'));
    final link = tester.getRect(find.text('Ver en el explorador').first);
    expect(card.top, lessThan(top.top));
    expect(card.bottom, greaterThan(link.bottom));
    expect(card.width, greaterThan(200));
  });

  testWidgets('cards carry the archetype copy and aligned pitches', (
    tester,
  ) async {
    await pumpAppAt(tester, '/arquetipos');
    expect(find.text('Creadores Ofensivos y Finalizadores'), findsOneWidget);
    expect(find.text('1.219 jugadores'), findsOneWidget);
    expect(find.textContaining('Delanteros, extremos'), findsOneWidget);
    final tops = tester
        .widgetList(find.byType(ArchetypePitch))
        .map((w) => tester.getTopLeft(find.byWidget(w)).dy)
        .toSet();
    expect(tops, hasLength(1));
    expect(find.text('Valor promedio'), findsNWidgets(3));
  });

  testWidgets('a representative player opens their dossier', (tester) async {
    final router = await pumpAppAt(tester, '/arquetipos');
    await tester.tap(find.text('Jugador 1000').first);
    await tester.pumpAndSettle();
    expect(location(router), '/explorador?jugador=1000');
  });

  testWidgets('"Ver en el explorador" filters the explorer by archetype', (
    tester,
  ) async {
    final router = await pumpAppAt(tester, '/arquetipos');
    await tester.tap(find.text('Ver en el explorador').last);
    await tester.pumpAndSettle();
    expect(location(router), '/explorador?arquetipo=2');
  });

  testWidgets('an unreachable server shows one panel', (tester) async {
    final backend = FakePlayersBackend()..failClusters = true;
    await pumpAppAt(tester, '/arquetipos', backend: backend);
    expect(
      find.text('No se pudo conectar con el servidor de datos'),
      findsOneWidget,
    );
    expect(find.byType(ShareBar), findsNothing);
  });
}
