// Tests for ReportRepository's stored-report lookup (GET /reports filtered
// by player) and for passing a cancel signal through to the client.
import 'dart:async';
import 'dart:convert';

import 'package:delphos_frontend/data/repositories/report_repository.dart';
import 'package:delphos_frontend/data/services/request_cancelled_exception.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import '../../support/http_fakes.dart';
import '../../support/report_fixtures.dart';

void main() {
  test('asks for the newest report of one player', () async {
    final log = <http.Request>[];
    final repo = ReportRepository(
      apiClient: fakeApi(
        (_) async => jsonResponse(reportListJson([reportJson('llm')])),
        log: log,
      ),
    );
    final report = await repo.latestFor(566723);
    final url = log.single.url;
    expect(url.path, '/reports');
    expect(url.queryParameters, {'player_id': '566723', 'limit': '1'});
    expect(report?.id, 7);
  });

  test('an empty list means no stored report', () async {
    final repo = ReportRepository(
      apiClient: fakeApi((_) async => jsonResponse(reportListJson([]))),
    );
    expect(await repo.latestFor(1), isNull);
  });

  test('a list body that breaks the contract is a FormatException', () {
    final repo = ReportRepository(
      apiClient: fakeApi((_) async => jsonResponse({'items': 'x'})),
    );
    expect(repo.latestFor(1), throwsFormatException);
  });

  test('a cancelled generation throws RequestCancelledException', () async {
    final never = Completer<http.Response>();
    final log = <http.Request>[];
    final repo = ReportRepository(
      apiClient: fakeApi((_) => never.future, log: log),
    );
    final cancel = Completer<void>();
    final call = repo.generate(1, forceRegenerate: true, cancel: cancel.future);
    await pumpEventQueue();
    cancel.complete();
    await expectLater(call, throwsA(isA<RequestCancelledException>()));
    expect(jsonDecode(log.single.body)['force_regenerate'], isTrue);
  });
}
