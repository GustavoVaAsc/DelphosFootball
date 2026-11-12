// A fake backend for the /reports endpoints: GET /reports answers at once
// with the stored report, if any; every POST /reports/generate is held until
// [ReportsBackend.answer], and either fails or returns a deterministic report.
import 'dart:async';
import 'dart:convert';

import 'package:delphos_frontend/data/repositories/report_repository.dart';
import 'package:http/http.dart' as http;

import 'http_fakes.dart';
import 'report_fixtures.dart';

/// Answers GET /reports at once and holds every generation until [answer].
class ReportsBackend {
  final List<http.Request> log = [];
  Map<String, Object?>? stored;
  bool failLookup = false;
  bool failGenerate = false;
  final List<Completer<void>> _gates = [];

  late final ReportRepository repository = ReportRepository(
    apiClient: fakeApi(_handle, log: log),
  );

  List<Object?> get generationBodies => [
    for (final r in log)
      if (r.method == 'POST') jsonDecode(r.body),
  ];

  Future<http.Response> _handle(http.Request request) async {
    if (request.method == 'GET') {
      if (failLookup) throw http.ClientException('offline', request.url);
      return jsonResponse(reportListJson([?stored]));
    }
    final gate = Completer<void>();
    _gates.add(gate);
    await gate.future;
    if (failGenerate) return problemResponse(503, 'Unavailable', 'No run');
    final id = jsonDecode(request.body)['player_id'] as int;
    return jsonResponse(reportJson('deterministic', id: 9, playerId: id));
  }

  void answer() {
    for (final gate in _gates) {
      if (!gate.isCompleted) gate.complete();
    }
  }
}
