// Tests for ArchetypesViewModel: /clusters plus four representative players
// per archetype, all in parallel; one failing list stays in its own card;
// a failing overview is the error state, and a retry recovers it.
import 'package:delphos_frontend/data/repositories/archetype_repository.dart';
import 'package:delphos_frontend/data/repositories/player_repository.dart';
import 'package:delphos_frontend/ui/core/view_models/section_status.dart';
import 'package:delphos_frontend/ui/features/archetypes/view_models/archetypes_view_model.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../../support/explorer_harness.dart';

void main() {
  late FakePlayersBackend backend;
  late ArchetypesViewModel vm;

  setUp(() {
    backend = FakePlayersBackend();
    vm = ArchetypesViewModel(
      archetypes: ArchetypeRepository(apiClient: backend.api),
      players: PlayerRepository(apiClient: backend.api),
    );
  });
  tearDown(() => vm.dispose());

  test('loads the overview and four players per archetype', () async {
    await vm.load();
    await backend.settle();
    expect(vm.overview.status, SectionStatus.ready);
    expect(vm.overview.value!.totalPlayers, 5522);
    final lists = backend.requests.where((u) => u.path == '/players');
    expect(lists.map((u) => u.queryParameters['cluster_id']).toSet(), {
      '0',
      '1',
      '2',
    });
    expect(lists.map((u) => u.queryParameters['page_size']).toSet(), {'4'});
    for (final id in [0, 1, 2]) {
      expect(vm.representatives(id).value, hasLength(4));
    }
  });

  test('a failing list stays inside its own card', () async {
    backend.failNext = true;
    await vm.load();
    await backend.settle();
    expect(vm.overview.status, SectionStatus.ready);
    final states = [
      for (final id in [0, 1, 2]) vm.representatives(id).status,
    ];
    expect(states.where((s) => s == SectionStatus.error), hasLength(1));
    expect(states.where((s) => s == SectionStatus.ready), hasLength(2));
  });

  test('a failing overview is an error, and loading again recovers', () async {
    backend.failClusters = true;
    await vm.load();
    await backend.settle();
    expect(vm.overview.status, SectionStatus.error);
    backend.failClusters = false;
    await vm.load();
    await backend.settle();
    expect(vm.overview.status, SectionStatus.ready);
  });
}
