// Design rules of the scouting assistant: no up/down colours in the step
// trail, no duplicate page title, and the answer capped at its measure.
import 'package:delphos_frontend/ui/core/theme/delphos_colors.dart';
import 'package:delphos_frontend/ui/core/theme/delphos_text.dart';
import 'package:delphos_frontend/ui/features/chat/view_models/chat_intro_gate.dart';
import 'package:delphos_frontend/ui/features/chat/views/chat_answer.dart';
import 'package:delphos_frontend/ui/features/chat/views/chat_header.dart';
import 'package:delphos_frontend/ui/features/chat/views/chat_step_trail.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';
import '../../../support/explorer_harness.dart';

Future<void> _ask(WidgetTester tester) async {
  await tester.tap(find.text('Entendido'));
  await tester.pumpAndSettle();
  await tester.enterText(find.byType(TextField), 'Hola');
  await tester.tap(find.text('Enviar'));
  await tester.pumpAndSettle();
}

void main() {
  setUp(ChatIntroGate.reset);

  testWidgets('the header repeats neither the page title nor "agente"', (
    tester,
  ) async {
    await pumpAppAt(tester, '/chat');

    expect(
      find.descendant(
        of: find.byType(ChatHeader),
        matching: find.text('Asistente de Scouting'),
      ),
      findsNothing,
    );
    expect(find.textContaining('agente'), findsNothing);
  });

  testWidgets('the step trail uses neither up nor down colours', (
    tester,
  ) async {
    final backend = FakePlayersBackend()
      ..chatSseBody =
          'event: tool\n'
          'data: {"tool":"search_players","ok":true,"summary":"Dos jugadores."}\n\n'
          'event: tool\n'
          'data: {"tool":"get_player_valuation","ok":false,"summary":"boom"}\n\n'
          'event: message\n'
          'data: {"session_id":"s","message":"Listo **Kane**.","model_run_id":"r","tools_called":[],"created_at":"2026-11-13T12:00:00Z"}\n\n';
    await pumpAppAt(tester, '/chat', backend: backend);
    await _ask(tester);

    expect(
      find.textContaining('No se pudo completar', findRichText: true),
      findsOneWidget,
    );
    expect(find.textContaining('boom', findRichText: true), findsNothing);

    final trail = find.byType(ChatStepTrail);
    const forbidden = [DelphosColors.up, DelphosColors.down];
    for (final box in tester.widgetList<DecoratedBox>(
      find.descendant(of: trail, matching: find.byType(DecoratedBox)),
    )) {
      final decoration = box.decoration;
      if (decoration is BoxDecoration) {
        expect(forbidden, isNot(contains(decoration.color)));
      }
    }
    for (final text in tester.widgetList<RichText>(
      find.descendant(of: trail, matching: find.byType(RichText)),
    )) {
      text.text.visitChildren((span) {
        if (span is TextSpan) {
          expect(forbidden, isNot(contains(span.style?.color)));
        }
        return true;
      });
    }
  });

  testWidgets('the answer is capped at 68 zero-widths', (tester) async {
    final style = DelphosText.prose();
    final zero = TextPainter(
      text: TextSpan(text: '0', style: style),
      textDirection: TextDirection.ltr,
    )..layout();
    await tester.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(),
        child: Directionality(
          textDirection: TextDirection.ltr,
          child: Align(
            alignment: Alignment.topLeft,
            child: SizedBox(
              width: 4000,
              child: ChatAnswer(text: 'palabra ' * 400),
            ),
          ),
        ),
      ),
    );

    final width = tester.getSize(find.byType(SelectableText)).width;
    expect(width, lessThanOrEqualTo(zero.width * 68 + 0.5));
  });
}
