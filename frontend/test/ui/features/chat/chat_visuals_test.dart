// Design rules of the scouting assistant: no up/down colours in the step
// trail, no duplicate page title, two-bubble turn alignment, and the answer
// capped at its Source Sans 3 measure.
import 'package:delphos_frontend/domain/models/chat_turn.dart';
import 'package:delphos_frontend/ui/core/theme/delphos_colors.dart';
import 'package:delphos_frontend/ui/core/theme/delphos_text.dart';
import 'package:delphos_frontend/ui/features/chat/view_models/chat_intro_gate.dart';
import 'package:delphos_frontend/ui/features/chat/views/chat_answer.dart';
import 'package:delphos_frontend/ui/features/chat/views/chat_assistant_bubble.dart';
import 'package:delphos_frontend/ui/features/chat/views/chat_hairline.dart';
import 'package:delphos_frontend/ui/features/chat/views/chat_header.dart';
import 'package:delphos_frontend/ui/features/chat/views/chat_step_trail.dart';
import 'package:delphos_frontend/ui/features/chat/views/chat_turn_card.dart';
import 'package:delphos_frontend/ui/features/chat/views/chat_user_bubble.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';
import '../../../support/explorer_harness.dart';

Future<void> _ask(WidgetTester tester, [String message = 'Hola']) async {
  await tester.tap(find.text('Entendido'));
  await tester.pumpAndSettle();
  await tester.enterText(find.byType(TextField), message);
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
        matching: find.text('PitIA'),
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

  testWidgets('the answer uses Source Sans 3 capped at ChatAnswer.measure', (
    tester,
  ) async {
    await loadArchivo();
    tester.view.physicalSize = const Size(1440, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);

    final style = ChatAnswer.bodyStyle();
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
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 4000),
              child: ChatAnswer(text: 'palabra ' * 400),
            ),
          ),
        ),
      ),
    );

    final selectable = tester.widget<SelectableText>(
      find.byType(SelectableText),
    );
    expect(selectable.textSpan?.style?.fontFamily, DelphosText.sansFamily);
    final width = tester.getSize(find.byType(SelectableText)).width;
    expect(width, lessThanOrEqualTo(zero.width * ChatAnswer.measure + 0.5));
  });

  testWidgets('turns render user prompts on the right and PitIA on the left', (
    tester,
  ) async {
    await pumpAppAt(tester, '/chat');
    await _ask(tester, 'Busca delanteros');

    final userBubble = find.byType(ChatUserBubble);
    final assistantBubble = find.byType(ChatAssistantBubble);
    expect(userBubble, findsOneWidget);
    expect(assistantBubble, findsOneWidget);

    final userBoxFinder = find.descendant(
      of: userBubble,
      matching: find.byType(Container),
    );
    final assistantBoxFinder = find.descendant(
      of: assistantBubble,
      matching: find.byWidgetPredicate(
        (w) =>
            w is Container &&
            w.decoration is BoxDecoration &&
            (w.decoration! as BoxDecoration).color == DelphosColors.surface,
      ),
    );

    final userRect = tester.getRect(userBoxFinder);
    final assistantRect = tester.getRect(assistantBoxFinder);
    expect(userRect.left, greaterThan(assistantRect.left));
    expect(userRect.right, greaterThan(assistantRect.right));

    final userBox = tester.widget<Container>(userBoxFinder);
    expect((userBox.decoration! as BoxDecoration).color, DelphosColors.ink);
    final userText = tester.widget<Text>(
      find.descendant(of: userBubble, matching: find.text('Busca delanteros')),
    );
    expect(userText.style?.color, DelphosColors.onSidebar);

    expect(
      find.descendant(of: assistantBubble, matching: find.text('PitIA')),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: assistantBubble,
        matching: find.ancestor(
          of: find.text('P'),
          matching: find.byType(ExcludeSemantics),
        ),
      ),
      findsOneWidget,
    );
  });

  testWidgets('a turn without assistant state renders no empty PitIA bubble', (
    tester,
  ) async {
    await tester.pumpWidget(
      const Directionality(
        textDirection: TextDirection.ltr,
        child: ChatTurnCard(turn: ChatTurn(userMessage: 'Hola')),
      ),
    );

    expect(find.byType(ChatUserBubble), findsOneWidget);
    expect(find.byType(ChatAssistantBubble), findsNothing);
  });

  testWidgets('an answer-only turn renders no leading hairline inside bubble', (
    tester,
  ) async {
    await loadArchivo();
    await tester.pumpWidget(
      const MediaQuery(
        data: MediaQueryData(),
        child: Directionality(
          textDirection: TextDirection.ltr,
          child: SizedBox(
            width: 880,
            child: ChatTurnCard(
              turn: ChatTurn(
                userMessage: 'Hola',
                assistantMessage: 'Respuesta directa.',
              ),
            ),
          ),
        ),
      ),
    );

    expect(find.byType(ChatAnswer), findsOneWidget);
    expect(find.byType(ChatHairline), findsNothing);
  });
}
