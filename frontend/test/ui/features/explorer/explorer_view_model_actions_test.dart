// Tests for ExplorerViewModel's actions: filters, debounced search, reset,
// pagination bounds, and opening and closing the dossier.
import 'package:delphos_frontend/data/repositories/player_repository.dart';
import 'package:delphos_frontend/domain/models/valuation_status.dart';
import 'package:delphos_frontend/routing/explorer_query.dart';
import 'package:delphos_frontend/ui/features/explorer/view_models/explorer_view_model.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../../support/explorer_harness.dart';

void main() {
  late FakePlayersBackend backend;
  late List<ExplorerQuery> navigations;
  late ExplorerViewModel vm;

  setUp(() {
    backend = FakePlayersBackend();
    navigations = [];
    vm = ExplorerViewModel(
      players: PlayerRepository(apiClient: backend.api),
      navigate: navigations.add,
      searchDebounce: const Duration(milliseconds: 20),
    );
  });
  tearDown(() => vm.dispose());

  group('filters', () {
    setUp(() async {
      vm.applyQuery(const ExplorerQuery(page: 4, playerId: 7));
      await backend.settle();
    });

    test('a filter change goes to page 1 and keeps the open player', () {
      vm.setStatusFilter(ValuationStatus.fair);
      vm.setPosition('Defender');
      vm.setCluster(1);
      expect(navigations.map((q) => q.page), everyElement(1));
      expect(navigations.map((q) => q.playerId), everyElement(7));
      expect(navigations[0].status, ValuationStatus.fair);
      expect(navigations[1].position, 'Defender');
      expect(navigations[2].clusterId, 1);
    });

    test('search is debounced, trimmed, and empty clears it', () async {
      vm.setSearchText('o');
      vm.setSearchText('ol');
      vm.setSearchText(' oli ');
      expect(vm.searchText, ' oli ');
      expect(navigations, isEmpty);
      await Future<void>.delayed(const Duration(milliseconds: 40));
      expect(navigations.single.search, 'oli');
      vm.setSearchText('   ');
      await Future<void>.delayed(const Duration(milliseconds: 40));
      expect(navigations.last.search, isNull);
    });

    test('reset clears every filter and keeps the open player', () {
      vm.applyQuery(
        const ExplorerQuery(position: 'Attack', search: 'x', playerId: 7),
      );
      vm.resetFilters();
      expect(navigations.single.hasFilters, isFalse);
      expect(navigations.single.playerId, 7);
      expect(vm.searchText, isEmpty);
    });
  });

  group('pages', () {
    test('stay inside 1..totalPages', () async {
      backend.total = 120;
      vm.applyQuery(const ExplorerQuery(page: 2));
      await backend.settle();
      vm.goToPage(0);
      vm.goToPage(4);
      expect(navigations, isEmpty);
      vm.goToPage(3);
      expect(navigations.single.page, 3);
    });

    test('a page past the end in the URL moves to the last page', () async {
      backend.total = 120;
      vm.applyQuery(const ExplorerQuery(page: 9));
      await backend.settle();
      expect(navigations.single.page, 3);
    });
  });

  group('dossier', () {
    test('a row toggles its dossier open and closed', () async {
      vm.applyQuery(const ExplorerQuery());
      await backend.settle();
      final id = backend.idOnPage(0);
      vm.togglePlayer(id);
      expect(navigations.last.playerId, id);
      vm.applyQuery(navigations.last);
      vm.togglePlayer(id);
      expect(navigations.last.playerId, isNull);
      vm.applyQuery(ExplorerQuery(playerId: id));
      vm.closeDossier();
      expect(navigations.last.playerId, isNull);
    });

    test('closes when a filter change drops its player', () async {
      vm.applyQuery(ExplorerQuery(playerId: backend.idOnPage(0)));
      await backend.settle();
      vm.applyQuery(ExplorerQuery(search: 'ab', playerId: backend.idOnPage(0)));
      await backend.settle();
      expect(navigations.single.playerId, isNull);
      expect(navigations.single.search, 'ab');
    });

    test('a deep link to a player off the first page stays open', () async {
      vm.applyQuery(const ExplorerQuery(playerId: 999999));
      await backend.settle();
      expect(navigations, isEmpty);
    });
  });
}
