// Widget tests for the conversational scouting assistant (/chat): auto-open
// capabilities pop-up and header reopen, natural-language tool-call step
// feedback (no literal function names), and graceful offline LLM handling.
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';
import '../../../support/explorer_harness.dart';

void main() {
  testWidgets(
    'capabilities pop-up opens automatically, closes on Entendido, and reopens',
    (tester) async {
      await pumpAppAt(tester, '/chat');

      expect(
        find.text('¿Qué puede hacer el asistente de scouting?'),
        findsOneWidget,
      );

      await tester.tap(find.text('Entendido'));
      await tester.pumpAndSettle();

      expect(
        find.text('¿Qué puede hacer el asistente de scouting?'),
        findsNothing,
      );

      await tester.tap(find.text('¿Qué puede hacer el agente?'));
      await tester.pumpAndSettle();

      expect(
        find.text('¿Qué puede hacer el asistente de scouting?'),
        findsOneWidget,
      );

      await tester.sendKeyEvent(LogicalKeyboardKey.escape);
      await tester.pumpAndSettle();

      expect(
        find.text('¿Qué puede hacer el asistente de scouting?'),
        findsNothing,
      );
    },
  );

  testWidgets(
    'tool steps display natural Spanish feedback without literal function names',
    (tester) async {
      final backend = FakePlayersBackend()
        ..chatSseBody =
            'event: tool\n'
            'data: {"tool":"search_players","ok":true,"summary":"La herramienta «search_players» devolvió 2 jugadores."}\n\n'
            'event: tool\n'
            'data: {"tool":"get_player_valuation","ok":true,"summary":"Se revisó la valoración y el diagnóstico de Harry Kane."}\n\n'
            'event: message\n'
            'data: {"session_id":"sess-2","message":"Harry Kane presenta infravaloración en 2025/26.","model_run_id":"run_test","tools_called":["search_players","get_player_valuation"],"created_at":"2026-11-13T12:00:00Z"}\n\n';
      await pumpAppAt(tester, '/chat', backend: backend);

      await tester.tap(find.text('Entendido'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byType(TextField),
        'Compara a Harry Kane con sus reemplazos',
      );
      await tester.tap(find.text('Enviar'));
      await tester.pumpAndSettle();

      expect(
        find.text('Pasos realizados sobre la base del modelo'),
        findsOneWidget,
      );
      expect(
        find.textContaining(
          'Búsqueda de jugadores en el mercado',
          findRichText: true,
        ),
        findsOneWidget,
      );
      expect(
        find.textContaining(
          'Análisis de valoración y brecha',
          findRichText: true,
        ),
        findsOneWidget,
      );
      expect(
        find.textContaining(
          'Se revisó la valoración y el diagnóstico de Harry Kane.',
          findRichText: true,
        ),
        findsOneWidget,
      );
      expect(
        find.textContaining(
          'Harry Kane presenta infravaloración en 2025/26.',
          findRichText: true,
        ),
        findsOneWidget,
      );

      // Literal function names must never be exposed to the user.
      expect(
        find.textContaining('search_players', findRichText: true),
        findsNothing,
      );
      expect(
        find.textContaining('get_player_valuation', findRichText: true),
        findsNothing,
      );
    },
  );

  testWidgets('uninitialized LLM server shows a clear Spanish notice', (
    tester,
  ) async {
    final backend = FakePlayersBackend()..chatUnavailable = true;
    await pumpAppAt(tester, '/chat', backend: backend);

    await tester.tap(find.text('Entendido'));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), 'Busca delanteros');
    await tester.tap(find.text('Enviar'));
    await tester.pumpAndSettle();

    expect(
      find.textContaining(
        'El servidor de lenguaje local aún no está inicializado',
      ),
      findsOneWidget,
    );
  });
}
