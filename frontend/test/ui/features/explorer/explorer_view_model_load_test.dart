// Tests for ExplorerViewModel's loading: URL query to request parameters,
// the states, refreshes that keep the rows, and stale responses.
import 'package:delphos_frontend/data/repositories/player_repository.dart';
import 'package:delphos_frontend/domain/models/valuation_status.dart';
import 'package:delphos_frontend/routing/explorer_query.dart';
import 'package:delphos_frontend/ui/features/explorer/view_models/explorer_status.dart';
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

  group('loading', () {
    test('turns the URL query into the request parameters', () async {
      vm.applyQuery(
        const ExplorerQuery(
          status: ValuationStatus.undervalued,
          position: 'Midfield',
          clusterId: 2,
          search: 'Pedri',
          page: 3,
        ),
      );
      expect(vm.status, ExplorerStatus.loading);
      await backend.settle();
      expect(backend.requests.single.queryParameters, {
        'name': 'Pedri',
        'position': 'Midfield',
        'valuation_status': 'undervalued',
        'cluster_id': '2',
        'page': '3',
        'page_size': '50',
      });
      expect(vm.status, ExplorerStatus.ready);
      expect(vm.page!.players, hasLength(backend.idsPerPage));
    });

    test('is empty when nobody matches', () async {
      backend.total = 0;
      vm.applyQuery(const ExplorerQuery(search: 'zzz'));
      await backend.settle();
      expect(vm.status, ExplorerStatus.empty);
    });

    test('fails on a network error and retries the same query', () async {
      backend.failNext = true;
      vm.applyQuery(const ExplorerQuery(position: 'Attack'));
      await backend.settle();
      expect(vm.status, ExplorerStatus.error);
      await vm.retry();
      expect(vm.status, ExplorerStatus.ready);
      expect(backend.requests, hasLength(2));
      expect(backend.requests.last.queryParameters['position'], 'Attack');
    });

    test('does not refetch when only the open player changes', () async {
      vm.applyQuery(const ExplorerQuery());
      await backend.settle();
      vm.applyQuery(ExplorerQuery(playerId: backend.idOnPage(0)));
      await backend.settle();
      expect(backend.requests, hasLength(1));
    });

    test('keeps the shown rows while the next page loads', () async {
      vm.applyQuery(const ExplorerQuery());
      await backend.settle();
      backend.hold = true;
      vm.applyQuery(const ExplorerQuery(page: 2));
      expect(vm.status, ExplorerStatus.ready);
      expect(vm.isRefreshing, isTrue);
      expect(vm.page!.page, 1);
      backend.release();
      await backend.settle();
      expect(vm.isRefreshing, isFalse);
      expect(vm.page!.page, 2);
    });

    test('ignores a response that a newer query overtook', () async {
      backend.hold = true;
      vm.applyQuery(const ExplorerQuery(search: 'a'));
      vm.applyQuery(const ExplorerQuery(search: 'ab'));
      backend.releaseInReverse();
      await backend.settle();
      expect(vm.query.search, 'ab');
      expect(vm.page!.players.first.name, startsWith('ab'));
    });
  });
}
