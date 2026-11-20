// Tests for ReportRepository against a fake backend: the request body, the
// report's provenance fields, and a stored report by id.
import 'dart:convert';

import 'package:delphos_frontend/data/repositories/report_repository.dart';
import 'package:delphos_frontend/data/services/api_exception.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import '../../support/http_fakes.dart';
import '../../support/report_fixtures.dart';

void main() {
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
      expect(report.promptVersion, 'v1-t0.7-p0.8-k20');
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
      expect(report.promptVersion, isNull);
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
