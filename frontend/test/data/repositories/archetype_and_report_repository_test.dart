// Tests for ArchetypeRepository and ReportRepository against a fake
// backend: parsing, the report request body, and report provenance.
import 'dart:convert';

import 'package:delphos_frontend/data/repositories/archetype_repository.dart';
import 'package:delphos_frontend/data/repositories/report_repository.dart';
import 'package:delphos_frontend/data/services/api_exception.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import '../../support/http_fakes.dart';
import '../../support/report_fixtures.dart';

void main() {
  group('ArchetypeRepository', () {
    test('parses the archetypes and totals their players', () async {
      Map<String, Object?> cluster(int id, int count) => {
        'cluster_id': id,
        'name': 'English name',
        'player_count': count,
        'avg_market_value_eur': 12500000.0,
        'avg_minutes': 1800.5,
        'avg_goals': 4.2,
        'avg_assists': 3,
      };
      final repo = ArchetypeRepository(
        apiClient: fakeApi(
          (_) async => jsonResponse({
            'model_run_id': 'run_2025_v1',
            'season': 2025,
            'clusters': [cluster(0, 1500), cluster(1, 2200), cluster(2, 1822)],
          }),
        ),
      );
      final overview = await repo.getOverview();
      expect(overview.season, 2025);
      expect(overview.archetypes, hasLength(3));
      expect(overview.archetypes[1].avgAssists, 3.0);
      expect(overview.totalPlayers, 5522);
    });
  });

  group('ReportRepository', () {
    test('posts the player id as JSON and parses the report', () async {
      final log = <http.Request>[];
      final repo = ReportRepository(
        apiClient: fakeApi(
          (_) async => jsonResponse(reportJson('llm')),
          log: log,
        ),
      );
      final report = await repo.generate(566723);
      final request = log.single;
      expect(request.method, 'POST');
      expect(request.url.path, '/reports/generate');
      expect(request.headers['Content-Type'], startsWith('application/json'));
      expect(jsonDecode(request.body), {
        'player_id': 566723,
        'report_type': 'scouting',
        'force_regenerate': false,
      });
      expect(report.id, 7);
      expect(report.html, startsWith('<p><strong>'));
      expect(report.writtenByModel, isTrue);
      expect(report.llmModel, 'qwen/qwen3.5-9b');
      expect(report.createdAt, DateTime.utc(2026, 11, 10, 18));
    });

    test('marks a deterministic report as not written by the model', () async {
      final repo = ReportRepository(
        apiClient: fakeApi(
          (_) async => jsonResponse(reportJson('deterministic')),
        ),
      );
      final report = await repo.generate(566723, forceRegenerate: true);
      expect(report.writtenByModel, isFalse);
      expect(report.llmModel, isNull);
    });

    test('reads a stored report and surfaces a 404', () async {
      final repo = ReportRepository(
        apiClient: fakeApi(
          (request) async => request.url.path == '/reports/7'
              ? jsonResponse(reportJson('llm'))
              : problemResponse(404, 'Not Found', 'Report not found'),
        ),
      );
      expect((await repo.getReport(7)).playerName, 'Michael Olise');
      await expectLater(
        repo.getReport(8),
        throwsA(isA<ApiException>().having((e) => e.isNotFound, '404', true)),
      );
    });
  });
}
