// Widget tests for the chat's "Conversaciones" menu: listing saved sessions
// with the loading, empty and error states, restoring one as completed turns,
// and keeping the conversation on show when the reader leaves the chat and
// comes back.
import 'package:delphos_frontend/routing/routes.dart';
import 'package:delphos_frontend/ui/core/widgets/action_button.dart';
import 'package:delphos_frontend/ui/features/chat/view_models/chat_intro_gate.dart';
import 'package:delphos_frontend/ui/features/chat/views/chat_sessions_panel.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../../support/app_harness.dart';
import '../../../support/chat_session_fixtures.dart';
import '../../../support/explorer_harness.dart';

const _a = '11111111-1111-4111-8111-111111111111';
const _b = '22222222-2222-4222-8222-222222222222';

FakePlayersBackend _backendWithSessions() => FakePlayersBackend()
  ..chatSessions = [
    chatSessionJson(_a, title: 'Busca delanteros infravalorados'),
    chatSessionJson(_b, title: 'Compara a Harry Kane'),
  ]
  ..chatMessages[_a] = [
    chatMessageJson('user', 'Busca delanteros infravalorados', n: 1),
    chatMessageJson('assistant', 'Encontré dos delanteros.', n: 2),
  ]
  ..chatMessages[_b] = [
    chatMessageJson('user', 'Compara a Harry Kane', n: 1),
    chatMessageJson('assistant', 'Kane está infravalorado.', n: 2),
  ];

Future<void> _openMenu(WidgetTester tester) async {
  await tester.tap(find.text('Entendido'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Conversaciones'));
  await tester.pumpAndSettle();
}

Finder _inPanel(Finder finder) =>
    find.descendant(of: find.byType(ChatSessionsPanel), matching: finder);

void main() {
  setUp(ChatIntroGate.reset);

  testWidgets('lists the saved sessions by title and date', (tester) async {
    await pumpAppAt(tester, '/chat', backend: _backendWithSessions());
    await _openMenu(tester);

    expect(
      _inPanel(find.text('Busca delanteros infravalorados')),
      findsOneWidget,
    );
    expect(_inPanel(find.text('Compara a Harry Kane')), findsOneWidget);
    expect(_inPanel(find.text('10 nov 2026')), findsNWidgets(2));
    expect(_inPanel(find.text('Nueva conversación')), findsOneWidget);
  });

  testWidgets('picking a session restores its question and answer', (
    tester,
  ) async {
    await pumpAppAt(tester, '/chat', backend: _backendWithSessions());
    await _openMenu(tester);

    await tester.tap(_inPanel(find.text('Compara a Harry Kane')));
    await tester.pumpAndSettle();

    expect(find.byType(ChatSessionsPanel), findsNothing);
    expect(find.text('Compara a Harry Kane'), findsOneWidget);
    expect(find.textContaining('Kane está infravalorado.'), findsOneWidget);
    // Tool turns are not stored: no trail on a restored turn.
    expect(
      find.text('Pasos realizados sobre la base del modelo'),
      findsNothing,
    );
  });

  testWidgets('a long session says it shows only the latest messages', (
    tester,
  ) async {
    final backend = _backendWithSessions()..chatMessageTotals[_b] = 250;
    await pumpAppAt(tester, '/chat', backend: backend);
    await _openMenu(tester);

    await tester.tap(_inPanel(find.text('Compara a Harry Kane')));
    await tester.pumpAndSettle();

    expect(find.text('Mostrando los últimos 2 mensajes'), findsOneWidget);
  });

  testWidgets('no saved sessions shows the empty sentence', (tester) async {
    await pumpAppAt(tester, '/chat');
    await _openMenu(tester);

    expect(
      _inPanel(find.text('Todavía no hay conversaciones guardadas.')),
      findsOneWidget,
    );
  });

  testWidgets('a failed list shows an error and Reintentar loads it', (
    tester,
  ) async {
    final backend = _backendWithSessions()..failChatSessions = true;
    await pumpAppAt(tester, '/chat', backend: backend);
    await _openMenu(tester);

    expect(
      _inPanel(find.text('No se pudieron cargar las conversaciones.')),
      findsOneWidget,
    );

    backend.failChatSessions = false;
    await tester.tap(_inPanel(find.text('Reintentar')));
    await tester.pumpAndSettle();

    expect(_inPanel(find.text('Compara a Harry Kane')), findsOneWidget);
  });

  testWidgets('shows the loading note while the list is held', (tester) async {
    final backend = _backendWithSessions();
    await pumpAppAt(tester, '/chat', backend: backend);
    await tester.tap(find.text('Entendido'));
    await tester.pumpAndSettle();

    backend.hold = true;
    await tester.tap(find.text('Conversaciones'));
    await tester.pump();

    expect(_inPanel(find.text('Cargando conversaciones…')), findsOneWidget);

    backend.release();
    await tester.pumpAndSettle();
    expect(_inPanel(find.text('Compara a Harry Kane')), findsOneWidget);
  });

  testWidgets('a session that cannot be opened offers Reintentar', (
    tester,
  ) async {
    final backend = _backendWithSessions()..chatMessages.remove(_a);
    await pumpAppAt(tester, '/chat', backend: backend);
    await _openMenu(tester);

    await tester.tap(_inPanel(find.text('Busca delanteros infravalorados')));
    await tester.pumpAndSettle();

    expect(find.text('No se pudo abrir la conversación'), findsOneWidget);

    backend.chatMessages[_a] = [
      chatMessageJson('user', 'Busca delanteros infravalorados', n: 1),
      chatMessageJson('assistant', 'Encontré dos delanteros.', n: 2),
    ];
    await tester.tap(find.text('Reintentar'));
    await tester.pumpAndSettle();

    expect(find.text('No se pudo abrir la conversación'), findsNothing);
    expect(find.textContaining('Encontré dos delanteros.'), findsOneWidget);
  });

  testWidgets('Nueva conversación in the menu starts an empty conversation', (
    tester,
  ) async {
    await pumpAppAt(tester, '/chat', backend: _backendWithSessions());
    await _openMenu(tester);
    await tester.tap(_inPanel(find.text('Compara a Harry Kane')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Conversaciones'));
    await tester.pumpAndSettle();

    await tester.tap(_inPanel(find.text('Nueva conversación')));
    await tester.pumpAndSettle();

    expect(find.byType(ChatSessionsPanel), findsNothing);
    expect(find.textContaining('Kane está infravalorado.'), findsNothing);
  });

  testWidgets('Escape closes the menu', (tester) async {
    await pumpAppAt(tester, '/chat', backend: _backendWithSessions());
    await _openMenu(tester);
    expect(find.byType(ChatSessionsPanel), findsOneWidget);

    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pumpAndSettle();

    expect(find.byType(ChatSessionsPanel), findsNothing);
    // Focus goes back to the "Conversaciones" button that opened the menu.
    final opener = find.ancestor(
      of: find.text('Conversaciones'),
      matching: find.byType(ActionButton),
    );
    final focused = FocusManager.instance.primaryFocus?.context;
    expect(focused, isNotNull);
    expect(
      find.descendant(
        of: opener,
        matching: find.byElementPredicate((element) => element == focused),
      ),
      findsOneWidget,
    );
  });

  testWidgets('leaving the chat and coming back keeps the conversation', (
    tester,
  ) async {
    final router = await pumpAppAt(
      tester,
      '/chat',
      backend: _backendWithSessions(),
    );
    await _openMenu(tester);
    await tester.tap(_inPanel(find.text('Compara a Harry Kane')));
    await tester.pumpAndSettle();

    router.go(Routes.explorer);
    await tester.pumpAndSettle();
    expect(find.textContaining('Kane está infravalorado.'), findsNothing);

    router.go(Routes.chat);
    await tester.pumpAndSettle();

    expect(find.textContaining('Kane está infravalorado.'), findsOneWidget);
    expect(find.byType(ChatSessionsPanel), findsNothing);
  });
}
