// Widget tests for the dossier content: the classifier lines, the shortfall
// note, the no-season state and the season guards, the full dossier on the
// explorer, and a replacements 404.
import 'package:delphos_frontend/data/models/player_valuation_dto.dart';
import 'package:delphos_frontend/data/models/replacements_dto.dart';
import 'package:delphos_frontend/domain/models/season_stats.dart';
import 'package:delphos_frontend/ui/features/explorer/views/replacements_list.dart';
import 'package:delphos_frontend/ui/features/explorer/views/season_section.dart';
import 'package:delphos_frontend/ui/features/explorer/views/valuation_section.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';
import '../../../support/dossier_fixtures.dart';
import '../../../support/explorer_harness.dart';

Future<void> pumpIn(WidgetTester tester, Widget child) async {
  await loadArchivo();
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(body: SizedBox(width: 400, child: child)),
    ),
  );
  await tester.pumpAndSettle();
}

Finder rich(String text) => find.textContaining(text, findRichText: true);

void main() {
  testWidgets('the classifier check reads the split and the probability', (
    tester,
  ) async {
    final valuation = PlayerValuationDto.fromJson(
      valuationJson(1, rf: true, dt: false),
    ).toDomain();
    await pumpIn(tester, ValuationSection(valuation: valuation));
    expect(find.text('Comprobación de los clasificadores'), findsOneWidget);
    expect(rich('71% de probabilidad de infravaloración'), findsOneWidget);
    expect(
      find.text('Random Forest y árbol de decisión no coinciden.'),
      findsOneWidget,
    );
    expect(find.textContaining('Diferencia +€95,9'), findsOneWidget);
  });

  testWidgets('a shortfall is a plain note above the rows, never padding', (
    tester,
  ) async {
    final set = ReplacementsDto.fromJson(
      replacementsJson(
        1,
        count: 1,
        shortfall: 'fewer_than_three_qualifying_peers',
      ),
    ).toDomain();
    await pumpIn(tester, ReplacementsList(set: set));
    expect(rich('1 de 3 reemplazos.'), findsOneWidget);
    expect(rich('Solo 1 jugador cumple todos los criterios'), findsOneWidget);
    expect(find.text('Candidato 1'), findsOneWidget);
    expect(find.text('Candidato 2'), findsNothing);
  });

  testWidgets('no season row prints one sentence', (tester) async {
    await pumpIn(tester, const SeasonSection(season: null));
    expect(
      find.text('Sin estadísticas de temporada para este jugador.'),
      findsOneWidget,
    );
  });

  testWidgets('impossible starts and shares print N/D', (tester) async {
    final season = SeasonStats(
      season: 2025,
      asOfDate: DateTime(2026, 5, 27),
      leagueId: 'L1',
      minutes: 900,
      apps: 15,
      starts: 20,
      goals: 1,
      assists: 1,
      yellowCards: 1,
      redCards: 0,
      starterRatio: 1.2,
      winRate: 2.47,
      cleanSheetRate: 0.3,
      goalsConcededPerMatch: 1,
      age: 22,
    );
    await pumpIn(tester, SeasonSection(season: season));
    expect(find.text('15 (N/D)'), findsOneWidget);
    expect(find.text('N/D'), findsOneWidget);
    expect(find.text('30%'), findsOneWidget);
  });

  testWidgets('the explorer dossier shows every section', (tester) async {
    await pumpAppAt(tester, '/explorador?jugador=1000');
    expect(find.text('Activo élite'), findsOneWidget);
    expect(rich('Edad 24'), findsOneWidget);
    expect(find.text('Precio de mercado'), findsOneWidget);
    expect(find.text('Temporada 2025/26'), findsOneWidget);
    expect(find.text('Reemplazos'), findsOneWidget);
    expect(find.text('Comparar reemplazos'), findsOneWidget);
    expect(find.text('Resumen'), findsOneWidget);
    expect(find.text('Generar informe'), findsOneWidget);
  });

  testWidgets('a replacements 404 is a sentence, not an error', (tester) async {
    final backend = FakePlayersBackend()..replacementsMissing = true;
    await pumpAppAt(tester, '/explorador?jugador=1000', backend: backend);
    expect(
      find.text('Este jugador no tiene reemplazos calculados.'),
      findsOneWidget,
    );
    expect(find.text('Reintentar'), findsNothing);
    expect(find.text('Precio de mercado'), findsOneWidget);
  });
}
