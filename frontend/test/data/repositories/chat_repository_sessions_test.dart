// Tests for ChatRepository's saved-session reads against a fake backend:
// the session list and one session's history.
import 'package:delphos_frontend/data/repositories/chat_repository.dart';
import 'package:delphos_frontend/data/services/api_exception.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import '../../support/chat_session_fixtures.dart';
import '../../support/http_fakes.dart';

const _id = '11111111-1111-4111-8111-111111111111';

void main() {
  group('ChatRepository.listSessions', () {
    test('parses titles and dates, keeping the backend order', () async {
      final log = <http.Request>[];
      final repo = ChatRepository(
        apiClient: fakeApi(
          (_) async => jsonResponse({
            'items': [
              chatSessionJson(_id, title: 'Busca delanteros'),
              chatSessionJson(
                '22222222-2222-4222-8222-222222222222',
                updatedAt: '2026-11-09T09:05:00Z',
              ),
            ],
            'total': 2,
          }),
          log: log,
        ),
      );

      final sessions = await repo.listSessions();

      expect(log.single.url.path, '/chat/sessions');
      expect(sessions, hasLength(2));
      expect(sessions[0].id, _id);
      expect(sessions[0].title, 'Busca delanteros');
      expect(sessions[0].updatedAt, DateTime.utc(2026, 11, 10, 9, 5));
      expect(sessions[1].title, isNull);
    });

    test('a body that breaks the contract is a FormatException', () async {
      final repo = ChatRepository(
        apiClient: fakeApi(
          (_) async => jsonResponse({
            'items': [
              {'id': _id},
            ],
            'total': 1,
          }),
        ),
      );

      expect(repo.listSessions(), throwsFormatException);
    });
  });

  group('ChatRepository.getSession', () {
    // The probe (limit 1) reports the total; the other request is the tail.
    Future<http.Response> history(http.Request request, {required int total}) {
      final query = request.url.queryParameters;
      final tail = [
        chatMessageJson('user', 'Busca delanteros', n: 1),
        chatMessageJson('assistant', 'Hay dos.', n: 2),
      ];
      return Future.value(
        jsonResponse(
          query['limit'] == '1'
              ? chatHistoryJson(_id, total: total, [tail.first])
              : chatHistoryJson(
                  _id,
                  title: 'Busca delanteros',
                  total: total,
                  offset: int.parse(query['offset'] ?? '0'),
                  tail,
                ),
        ),
      );
    }

    test(
      'reads the total, then the messages in order with the title',
      () async {
        final log = <http.Request>[];
        final repo = ChatRepository(
          apiClient: fakeApi((request) => history(request, total: 2), log: log),
        );

        final history_ = await repo.getSession(_id);

        expect(log, hasLength(2));
        expect(log.first.url.path, '/chat/sessions/$_id');
        expect(log.first.url.queryParameters, {'limit': '1'});
        expect(log.last.url.queryParameters, {'limit': '200', 'offset': '0'});
        expect(history_.sessionId, _id);
        expect(history_.title, 'Busca delanteros');
        expect(history_.messages.map((m) => m.role), ['user', 'assistant']);
        expect(history_.total, 2);
      },
    );

    test('a session longer than one page yields its latest messages', () async {
      final log = <http.Request>[];
      final repo = ChatRepository(
        apiClient: fakeApi((request) => history(request, total: 250), log: log),
      );

      final history_ = await repo.getSession(_id);

      expect(log.last.url.queryParameters['offset'], '50');
      expect(history_.total, 250);
      expect(history_.messages, hasLength(2));
    });

    test('an unknown session is an ApiException with 404', () async {
      final repo = ChatRepository(
        apiClient: fakeApi(
          (_) async =>
              problemResponse(404, 'Not Found', 'Chat session not found'),
        ),
      );

      expect(
        repo.getSession(_id),
        throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 404)),
      );
    });
  });
}
