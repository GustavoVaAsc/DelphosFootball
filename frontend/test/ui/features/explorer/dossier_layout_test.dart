// Layout tests for the dossier at its 440 px panel width: the Reemplazos
// subtitle stays on one line with "≥ 20%" unbroken, and the season grid's
// labels wrap instead of truncating, with every row's values aligned.
import 'package:delphos_frontend/domain/models/season_stats.dart';
import 'package:delphos_frontend/ui/core/theme/type_scale.dart';
import 'package:delphos_frontend/ui/features/explorer/views/season_section.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';

const replacementsSubtitle = 'Mismo arquetipo y posición · ahorro ≥ 20%';

void main() {
  testWidgets('the Reemplazos subtitle is one unbroken line', (tester) async {
    await pumpAppAt(tester, '/explorador?jugador=1000');
    final subtitle = find.text(replacementsSubtitle);
    expect(subtitle, findsOneWidget);
    // One 12 px line; a second line would make it at least 24 px tall.
    expect(
      tester.getSize(subtitle).height,
      lessThan(TypeScale.secondary * 1.8),
    );
    final button = tester.getRect(find.text('Comparar reemplazos'));
    expect(button.top, greaterThan(tester.getRect(subtitle).bottom));
  });

  testWidgets('season labels wrap and values stay aligned', (tester) async {
    await loadArchivo();
    final season = SeasonStats(
      season: 2025,
      asOfDate: DateTime(2026, 5, 27),
      leagueId: 'L1',
      minutes: 2400,
      apps: 30,
      starts: 28,
      goals: 0,
      assists: 1,
      yellowCards: 3,
      redCards: 0,
      starterRatio: 0.9,
      winRate: 0.5,
      cleanSheetRate: 0.3,
      goalsConcededPerMatch: 1.25,
      age: 29,
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Align(
            alignment: Alignment.topLeft,
            child: SizedBox(width: 392, child: SeasonSection(season: season)),
          ),
        ),
      ),
    );
    final label = tester.renderObject<RenderParagraph>(
      find.text('Goles recibidos/p'),
    );
    expect(label.didExceedMaxLines, isFalse);
    final valueTops = {
      for (final v in ['50%', '30%', '1,25', '3 / 0'])
        tester.getTopLeft(find.text(v)).dy,
    };
    expect(valueTops, hasLength(1));
  });
}
