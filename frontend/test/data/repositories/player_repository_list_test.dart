// Tests for PlayerRepository.listPlayers against a fake backend: query
// parameters, page parsing, optional fields, and contract drift.
import 'package:delphos_frontend/data/repositories/player_repository.dart';
import 'package:delphos_frontend/domain/models/player_query.dart';
import 'package:delphos_frontend/domain/models/valuation_status.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import '../../support/http_fakes.dart';
import '../../support/player_fixtures.dart';

void main() {
  group('listPlayers', () {
    test('sends only the filters that are set, with the API values', () async {
      final log = <http.Request>[];
      final repo = PlayerRepository(
        apiClient: fakeApi(
          (_) async => jsonResponse(listJson([summaryJson()])),
          log: log,
        ),
      );
      await repo.listPlayers(
        const PlayerQuery(
          name: '  Olise ',
          valuationStatus: ValuationStatus.undervalued,
          clusterId: 0,
          page: 2,
        ),
      );
      final uri = log.single.url;
      expect(uri.path, '/players');
      expect(uri.queryParameters, {
        'name': 'Olise',
        'valuation_status': 'undervalued',
        'cluster_id': '0',
        'page': '2',
        'page_size': '20',
      });
      expect(log.single.headers['Accept'], 'application/json');
    });

    test('parses the page and tolerates absent estimate and age', () async {
      final repo = PlayerRepository(
        apiClient: fakeApi(
          (_) async => jsonResponse(listJson([summaryJson()])),
        ),
      );
      final page = await repo.listPlayers(const PlayerQuery());
      expect(page.total, 5522);
      expect(page.totalPages, 277);
      expect(page.modelRunId, 'run_2025_v1');
      final player = page.players.single;
      expect(player.id, 566723);
      expect(player.subPosition, 'Right Winger');
      expect(player.marketValueEur, closeTo(150e6, 1));
      expect(player.valuationStatus, ValuationStatus.fair);
      expect(player.fairValueEur, isNull);
      expect(player.age, isNull);
      expect(player.imageUrl, isNull);
    });

    test('reads estimate and age once the backend sends them', () async {
      final item = summaryJson(
        extra: {'fair_value_eur': 190799569, 'age': 24.5},
      );
      final repo = PlayerRepository(
        apiClient: fakeApi((_) async => jsonResponse(listJson([item]))),
      );
      final player = (await repo.listPlayers(const PlayerQuery())).players[0];
      expect(player.fairValueEur, 190799569.0);
      expect(player.age, 24.5);
    });

    test('maps an unknown status to null instead of failing', () async {
      final item = summaryJson(extra: {'valuation_status': 'mystery'});
      final repo = PlayerRepository(
        apiClient: fakeApi((_) async => jsonResponse(listJson([item]))),
      );
      final page = await repo.listPlayers(const PlayerQuery());
      expect(page.players.single.valuationStatus, isNull);
    });

    test('rejects a page size above 100 or a page below 1 locally', () async {
      final log = <http.Request>[];
      final repo = PlayerRepository(
        apiClient: fakeApi((_) async => jsonResponse(listJson([])), log: log),
      );
      expect(
        () => repo.listPlayers(const PlayerQuery(pageSize: 101)),
        throwsArgumentError,
      );
      expect(
        () => repo.listPlayers(const PlayerQuery(page: 0)),
        throwsArgumentError,
      );
      expect(log, isEmpty);
    });

    test('fails loudly when a required field is missing', () async {
      final item = summaryJson()..remove('name');
      final repo = PlayerRepository(
        apiClient: fakeApi((_) async => jsonResponse(listJson([item]))),
      );
      expect(
        repo.listPlayers(const PlayerQuery()),
        throwsA(isA<FormatException>()),
      );
    });

    test('fails loudly when an optional field has the wrong type', () async {
      final item = summaryJson(extra: {'market_value_eur': '150M'});
      final repo = PlayerRepository(
        apiClient: fakeApi((_) async => jsonResponse(listJson([item]))),
      );
      expect(
        repo.listPlayers(const PlayerQuery()),
        throwsA(isA<FormatException>()),
      );
    });
  });
}
