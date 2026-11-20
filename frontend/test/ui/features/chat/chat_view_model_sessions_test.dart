// Tests for restoring a saved conversation in ChatViewModel: its messages
// become completed turns without tool steps, the next message continues the
// session, a failure leaves the conversation as it was, and a late answer
// for a superseded pick is ignored.
import 'dart:async';
import 'dart:convert';

import 'package:delphos_frontend/data/repositories/chat_repository.dart';
import 'package:delphos_frontend/ui/features/chat/view_models/chat_intro_gate.dart';
import 'package:delphos_frontend/ui/features/chat/view_models/chat_view_model.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import '../../../support/chat_session_fixtures.dart';
import '../../../support/http_fakes.dart';

const _a = '11111111-1111-4111-8111-111111111111';
const _b = '22222222-2222-4222-8222-222222222222';

const _sse =
    'event: message\n'
    'data: {"session_id":"$_a","message":"Respuesta nueva.","model_run_id":"r","tools_called":[],"created_at":"2026-11-13T12:00:00Z"}\n\n';

void main() {
  late List<http.Request> log;
  late Map<String, Completer<void>> gates;
  late Set<String> missing;
  int? historyTotal;
  late ChatViewModel vm;

  setUp(() {
    ChatIntroGate.reset();
    log = [];
    gates = {};
    missing = {};
    historyTotal = null;
    final api = fakeApi((request) async {
      final segments = request.url.pathSegments;
      if (request.method == 'POST') {
        return http.Response.bytes(
          utf8.encode(_sse),
          200,
          headers: {'content-type': 'text/event-stream; charset=utf-8'},
        );
      }
      if (segments.length == 3) {
        final id = segments.last;
        await gates[id]?.future;
        if (missing.contains(id)) {
          return problemResponse(404, 'Not Found', 'Chat session not found');
        }
        return jsonResponse(
          chatHistoryJson(id, title: 'Sesión $id', total: historyTotal, [
            chatMessageJson('user', 'Pregunta de $id', n: 1),
            chatMessageJson('assistant', 'Respuesta de $id', n: 2),
          ]),
        );
      }
      return jsonResponse({'items': [], 'total': 0});
    }, log: log);
    vm = ChatViewModel(repository: ChatRepository(apiClient: api));
  });

  tearDown(() => vm.dispose());

  Future<void> settle() async {
    for (var i = 0; i < 5; i++) {
      await Future<void>.delayed(Duration.zero);
    }
  }

  test('opening a session shows its messages as completed turns', () async {
    final opening = vm.openSession(_a);
    expect(vm.isRestoring, isTrue);
    await opening;

    expect(vm.isRestoring, isFalse);
    expect(vm.sessionId, _a);
    expect(vm.turns, hasLength(1));
    expect(vm.turns.single.userMessage, 'Pregunta de $_a');
    expect(vm.turns.single.assistantMessage, 'Respuesta de $_a');
    expect(vm.turns.single.steps, isEmpty);
    expect(vm.turns.single.isStreaming, isFalse);
  });

  test('the next message continues the restored session', () async {
    await vm.openSession(_a);
    await vm.sendMessage('Otra pregunta');

    final post = log.firstWhere((r) => r.method == 'POST');
    final body = jsonDecode(post.body) as Map<String, Object?>;
    expect(body['session_id'], _a);
    expect(vm.turns, hasLength(2));
    expect(vm.turns.last.assistantMessage, 'Respuesta nueva.');
  });

  test('opening a session replaces the conversation on show', () async {
    await vm.sendMessage('Pregunta suelta');
    expect(vm.turns.single.userMessage, 'Pregunta suelta');

    await vm.openSession(_b);

    expect(vm.sessionId, _b);
    expect(vm.turns.single.userMessage, 'Pregunta de $_b');
  });

  test('a failure keeps the conversation, and retry works', () async {
    await vm.openSession(_a);
    missing.add(_b);

    await vm.openSession(_b);

    expect(vm.restoreFailed, isTrue);
    expect(vm.isRestoring, isFalse);
    expect(vm.sessionId, _a);
    expect(vm.turns.single.userMessage, 'Pregunta de $_a');

    missing.clear();
    await vm.retryRestore();

    expect(vm.restoreFailed, isFalse);
    expect(vm.sessionId, _b);
  });

  test('a new conversation clears a failed restore', () async {
    missing.add(_b);
    await vm.openSession(_b);
    expect(vm.restoreFailed, isTrue);

    vm.clearConversation();

    expect(vm.restoreFailed, isFalse);
    expect(vm.turns, isEmpty);
    expect(vm.sessionId, isNull);
  });

  test('a late answer for a superseded pick is ignored', () async {
    gates[_a] = Completer<void>();
    final first = vm.openSession(_a);
    final second = vm.openSession(_b);
    await second;

    gates[_a]!.complete();
    await first;
    await settle();

    expect(vm.sessionId, _b);
    expect(vm.turns.single.userMessage, 'Pregunta de $_b');
  });

  test('no message is sent while a session loads', () async {
    gates[_a] = Completer<void>();
    final opening = vm.openSession(_a);

    await vm.sendMessage('Demasiado pronto');

    expect(log.where((r) => r.method == 'POST'), isEmpty);
    gates[_a]!.complete();
    await opening;
  });

  test('opening the session on show only closes the menu', () async {
    await vm.openSession(_a);
    vm.sessions.open();
    int reads() => log.where((r) => r.url.path == '/chat/sessions/$_a').length;
    final before = reads();

    await vm.openSession(_a);

    expect(vm.sessions.isOpen, isFalse);
    expect(reads(), before);
  });

  test(
    'a session longer than the page says how many messages it shows',
    () async {
      historyTotal = 250;
      await vm.openSession(_a);
      expect(vm.shownMessages, 2);

      vm.clearConversation();
      expect(vm.shownMessages, isNull);

      historyTotal = null;
      await vm.openSession(_a);
      expect(vm.shownMessages, isNull);
    },
  );
}
