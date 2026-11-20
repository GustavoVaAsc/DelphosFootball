// Tests for the "Conversaciones" menu state: loading on open, an empty list,
// a failure with retry, and a refresh that keeps the list on show.
import 'package:delphos_frontend/data/repositories/chat_repository.dart';
import 'package:delphos_frontend/ui/core/view_models/section_status.dart';
import 'package:delphos_frontend/ui/features/chat/view_models/chat_sessions_view_model.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import '../../../support/chat_session_fixtures.dart';
import '../../../support/http_fakes.dart';

const _id = '11111111-1111-4111-8111-111111111111';

void main() {
  late List<Map<String, Object?>> items;
  late bool fail;
  late int calls;
  late ChatSessionsViewModel vm;

  setUp(() {
    items = [chatSessionJson(_id, title: 'Busca delanteros')];
    fail = false;
    calls = 0;
    final repository = ChatRepository(
      apiClient: fakeApi((http.Request request) async {
        calls++;
        if (fail) throw http.ClientException('offline', request.url);
        return jsonResponse({'items': items, 'total': items.length});
      }),
    );
    vm = ChatSessionsViewModel(repository: repository);
  });

  tearDown(() => vm.dispose());

  Future<void> settle() async {
    for (var i = 0; i < 5; i++) {
      await Future<void>.delayed(Duration.zero);
    }
  }

  test('is closed and loading before it is opened', () {
    expect(vm.isOpen, isFalse);
    expect(vm.sessions.status, SectionStatus.loading);
    expect(calls, 0);
  });

  test('opening loads the sessions', () async {
    vm.open();
    expect(vm.isOpen, isTrue);
    expect(vm.sessions.status, SectionStatus.loading);

    await settle();

    expect(vm.sessions.status, SectionStatus.ready);
    expect(vm.sessions.value!.single.title, 'Busca delanteros');
  });

  test('no saved sessions is a ready, empty list', () async {
    items = [];
    vm.open();
    await settle();

    expect(vm.sessions.status, SectionStatus.ready);
    expect(vm.sessions.value, isEmpty);
  });

  test('a failure shows an error, and retry loads the list', () async {
    fail = true;
    vm.open();
    await settle();
    expect(vm.sessions.status, SectionStatus.error);

    fail = false;
    await vm.retry();

    expect(vm.sessions.status, SectionStatus.ready);
  });

  test('reopening reloads the list but keeps the old one on show', () async {
    vm.open();
    await settle();
    vm.close();
    items = [chatSessionJson('22222222-2222-4222-8222-222222222222')];

    vm.open();
    expect(vm.sessions.status, SectionStatus.ready);
    expect(vm.sessions.value!.single.id, _id);
    await settle();

    expect(calls, 2);
    expect(
      vm.sessions.value!.single.id,
      '22222222-2222-4222-8222-222222222222',
    );
  });

  test('a failed refresh keeps the list already on show', () async {
    vm.open();
    await settle();
    vm.close();
    fail = true;

    vm.open();
    await settle();

    expect(vm.sessions.status, SectionStatus.ready);
    expect(vm.sessions.value!.single.id, _id);
  });
}
