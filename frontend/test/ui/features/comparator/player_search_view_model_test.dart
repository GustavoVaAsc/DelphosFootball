// Tests for the comparator's player search: one debounced request of up to
// ten names, nothing for an empty field, stale answers dropped, keyboard
// highlight bounds, and a failed search.

import 'package:delphos_frontend/data/repositories/player_repository.dart';
import 'package:delphos_frontend/ui/features/comparator/view_models/player_search_view_model.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../../support/explorer_harness.dart';

void main() {
  late FakePlayersBackend backend;
  late PlayerSearchViewModel vm;

  setUp(() {
    backend = FakePlayersBackend();
    vm = PlayerSearchViewModel(
      players: PlayerRepository(apiClient: backend.api),
      debounce: const Duration(milliseconds: 20),
    );
  });
  tearDown(() => vm.dispose());

  Future<void> wait() async {
    await Future<void>.delayed(const Duration(milliseconds: 40));
    await backend.settle();
  }

  test('typing sends one debounced request for up to ten names', () async {
    vm.setText('o');
    vm.setText('ol');
    vm.setText(' oli ');
    expect(vm.text, ' oli ');
    expect(backend.requests, isEmpty);
    await wait();
    expect(backend.requests.single.queryParameters, {
      'name': 'oli',
      'page': '1',
      'page_size': '10',
    });
    expect(vm.isOpen, isTrue);
    expect(vm.results, hasLength(10));
    expect(vm.highlighted, 0);
  });

  test('an empty field closes the list and asks for nothing', () async {
    vm.setText('   ');
    await wait();
    expect(backend.requests, isEmpty);
    expect(vm.isOpen, isFalse);
    expect(vm.results, isEmpty);
  });

  test('a slower earlier answer does not replace a newer one', () async {
    backend.hold = true;
    vm.setText('a');
    await Future<void>.delayed(const Duration(milliseconds: 40));
    vm.setText('ab');
    await Future<void>.delayed(const Duration(milliseconds: 40));
    backend.releaseInReverse();
    await backend.settle();
    expect(vm.results.first.name, startsWith('ab'));
  });

  test('the highlight moves within the results and closes on demand', () async {
    vm.setText('oli');
    await wait();
    vm.moveHighlight(-1);
    expect(vm.highlighted, 0);
    vm.moveHighlight(3);
    expect(vm.highlighted, 3);
    vm.moveHighlight(50);
    expect(vm.highlighted, 9);
    expect(vm.highlightedPlayer, vm.results[9]);
    vm.close();
    expect(vm.isOpen, isFalse);
  });

  test('a failed search says so and keeps the list open', () async {
    backend.failNext = true;
    vm.setText('oli');
    await wait();
    expect(vm.failed, isTrue);
    expect(vm.isOpen, isTrue);
    expect(vm.results, isEmpty);
  });
}
