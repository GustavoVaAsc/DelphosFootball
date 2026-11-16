// Error mapping of the scouting assistant: fixed plain Spanish sentences, the
// backend's raw detail never shown, and "Reintentar" resending the turn.
import 'package:delphos_frontend/ui/features/chat/view_models/chat_intro_gate.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';
import '../../../support/explorer_harness.dart';

Future<void> _ask(WidgetTester tester, String text) async {
  await tester.tap(find.text('Entendido'));
  await tester.pumpAndSettle();
  await tester.enterText(find.byType(TextField), text);
  await tester.tap(find.text('Enviar'));
  await tester.pumpAndSettle();
}

void main() {
  setUp(ChatIntroGate.reset);

  testWidgets('an error event never shows the backend detail', (tester) async {
    final backend = FakePlayersBackend()
      ..chatSseBody =
          'event: error\n'
          'data: {"detail":"servicio de inferencia caido: traceback"}\n\n';
    await pumpAppAt(tester, '/chat', backend: backend);
    await _ask(tester, 'Busca delanteros');

    expect(find.textContaining('El asistente se interrumpió'), findsOneWidget);
    expect(find.textContaining('inferencia'), findsNothing);
    expect(find.textContaining('traceback'), findsNothing);
  });

  testWidgets('Reintentar resends the failed turn and replaces it', (
    tester,
  ) async {
    final backend = FakePlayersBackend()..chatUnavailable = true;
    await pumpAppAt(tester, '/chat', backend: backend);
    await _ask(tester, 'Busca delanteros');

    expect(find.text('Reintentar'), findsOneWidget);
    backend.chatUnavailable = false;
    await tester.tap(find.text('Reintentar'));
    await tester.pumpAndSettle();

    expect(find.text('Busca delanteros'), findsOneWidget);
    expect(find.text('Reintentar'), findsNothing);
    expect(
      find.textContaining(
        'Harry Kane presenta infravaloración',
        findRichText: true,
      ),
      findsOneWidget,
    );
  });
}
