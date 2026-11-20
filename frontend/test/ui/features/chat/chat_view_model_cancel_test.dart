// Tests for what a cancelled chat turn may and may not change. The fake
// backend streams `/chat` by hand and, like a real browser fetch that was
// already read, keeps delivering after the abort: a late event or a late
// error of a turn that was cleared or replaced must change nothing.
import 'dart:async';
import 'dart:convert';

import 'package:delphos_frontend/data/repositories/chat_repository.dart';
import 'package:delphos_frontend/data/services/api_client.dart';
import 'package:delphos_frontend/ui/features/chat/view_models/chat_intro_gate.dart';
import 'package:delphos_frontend/ui/features/chat/view_models/chat_view_model.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import '../../../support/chat_session_fixtures.dart';
import '../../../support/http_fakes.dart';

const _restored = '33333333-3333-4333-8333-333333333333';

class _Backend {
  final List<StreamController<List<int>>> posts = [];
  bool historyMissing = false;
  bool failPost = false;
  Completer<void>? historyGate;

  late final ApiClient api = ApiClient(
    baseUrl: testBaseUrl,
    httpClient: MockClient.streaming(_handle),
  );

  Future<http.StreamedResponse> _handle(
    http.BaseRequest request,
    http.ByteStream body,
  ) async {
    if (request.method == 'POST') {
      if (failPost) return _json(503, _problem(503));
      final stream = StreamController<List<int>>();
      posts.add(stream);
      return http.StreamedResponse(
        stream.stream,
        200,
        headers: {'content-type': 'text/event-stream; charset=utf-8'},
      );
    }
    await historyGate?.future;
    if (historyMissing) return _json(404, _problem(404));
    return _json(
      200,
      chatHistoryJson(_restored, [
        chatMessageJson('user', 'Pregunta guardada', n: 1),
        chatMessageJson('assistant', 'Respuesta guardada.', n: 2),
      ]),
    );
  }

  static Map<String, Object?> _problem(int status) => {
    'type': 'about:blank',
    'title': 'Error',
    'status': status,
    'detail': 'x',
    'trace_id': null,
  };

  static http.StreamedResponse _json(int status, Object body) =>
      http.StreamedResponse(
        Stream.value(utf8.encode(jsonEncode(body))),
        status,
        headers: {'content-type': 'application/json'},
      );
}

List<int> _sse(String event, Map<String, Object?> data) =>
    utf8.encode('event: $event\ndata: ${jsonEncode(data)}\n\n');

Map<String, Object?> _message(String sessionId) => {
  'session_id': sessionId,
  'message': 'Respuesta.',
  'model_run_id': 'r',
  'tools_called': <String>[],
  'created_at': '2026-11-13T12:00:00Z',
};

Future<void> _settle() async {
  for (var i = 0; i < 5; i++) {
    await Future<void>.delayed(Duration.zero);
  }
}

void main() {
  late _Backend backend;
  late ChatViewModel vm;

  setUp(() {
    ChatIntroGate.reset();
    backend = _Backend();
    vm = ChatViewModel(repository: ChatRepository(apiClient: backend.api));
  });
  tearDown(() => vm.dispose());

  test('a late message of a cleared turn does not set the session', () async {
    final sending = vm.sendMessage('Hola');
    await _settle();
    vm.clearConversation();

    backend.posts[0].add(_sse('message', _message('late')));
    await backend.posts[0].close();
    await sending;

    expect(vm.sessionId, isNull);
    expect(vm.turns, isEmpty);
    expect(vm.isBusy, isFalse);
  });

  test('a late message does not replace the session just opened', () async {
    final sending = vm.sendMessage('Hola');
    await _settle();
    await vm.openSession(_restored);

    backend.posts[0].add(_sse('message', _message('late')));
    await backend.posts[0].close();
    await sending;

    expect(vm.sessionId, _restored);
    expect(vm.turns.single.userMessage, 'Pregunta guardada');
  });

  test('an error after a clear changes nothing and throws nothing', () async {
    final sending = vm.sendMessage('Hola');
    await _settle();
    vm.clearConversation();

    backend.posts[0].addError(http.ClientException('aborted'));
    await sending;

    expect(vm.turns, isEmpty);
  });

  test('an error after a restore does not fail the restored turn', () async {
    final sending = vm.sendMessage('Hola');
    await _settle();
    await vm.openSession(_restored);

    backend.posts[0].addError(http.ClientException('aborted'));
    await sending;

    expect(vm.turns.single.errorMessage, isNull);
    expect(vm.turns.single.assistantMessage, 'Respuesta guardada.');
  });

  test('a superseded turn leaves the busy flag of the new one', () async {
    final first = vm.sendMessage('Uno');
    await _settle();
    vm.clearConversation();
    final second = vm.sendMessage('Dos');
    await _settle();
    expect(vm.isBusy, isTrue);

    await backend.posts[0].close();
    await first;
    expect(vm.isBusy, isTrue);

    backend.posts[1].add(_sse('message', _message('s2')));
    await backend.posts[1].close();
    await second;
    expect(vm.isBusy, isFalse);
    expect(vm.sessionId, 's2');
  });

  test('retryRestore cancels a turn in flight', () async {
    backend.historyMissing = true;
    await vm.openSession(_restored);
    expect(vm.restoreFailed, isTrue);
    backend.historyMissing = false;
    final sending = vm.sendMessage('Hola');
    await _settle();
    expect(vm.isBusy, isTrue);

    await vm.retryRestore();

    expect(vm.isBusy, isFalse);
    expect(vm.turns.single.userMessage, 'Pregunta guardada');
    backend.posts[0].add(_sse('message', _message('late')));
    await backend.posts[0].close();
    await sending;
    expect(vm.sessionId, _restored);
    expect(vm.turns, hasLength(1));
  });

  test('a failed turn cannot be retried while a session loads', () async {
    backend.failPost = true;
    await vm.sendMessage('Hola');
    expect(vm.canRetry, isTrue);

    backend.historyGate = Completer<void>();
    final opening = vm.openSession(_restored);
    await _settle();
    expect(vm.isRestoring, isTrue);
    expect(vm.canRetry, isFalse);

    await vm.retryLastTurn();
    expect(vm.turns.single.userMessage, 'Hola');
    expect(vm.turns.single.errorMessage, isNotNull);

    backend.historyGate!.complete();
    await opening;
    expect(vm.turns.single.userMessage, 'Pregunta guardada');
  });

  test(
    'a turn cancelled for a session that fails to load can be retried',
    () async {
      final sending = vm.sendMessage('Hola');
      await _settle();
      backend.posts[0].add(
        _sse('tool_start', {'step': 1, 'tool': 'search_players'}),
      );
      await _settle();
      expect(vm.turns.single.isStreaming, isTrue);

      backend.historyMissing = true;
      await vm.openSession(_restored);
      backend.posts[0].add(_sse('message', _message('late')));
      await backend.posts[0].close();
      await sending;

      final turn = vm.turns.single;
      expect(turn.isStreaming, isFalse);
      expect(turn.errorMessage, 'Se interrumpió la respuesta.');
      expect(turn.steps.single.isRunning, isFalse);
      expect(vm.canRetry, isTrue);
      expect(vm.sessionId, isNull);
    },
  );
}
