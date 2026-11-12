/// Scouting reports: the `/reports` endpoints of the backend, generation
/// (`POST /reports/generate`) and the stored list (`GET /reports`).
library;

import '../../domain/models/scouting_report.dart';
import '../models/report_dto.dart';
import '../services/api_client.dart';

/// Generates and reads scouting reports.
class ReportRepository {
  ReportRepository({required ApiClient apiClient}) : _api = apiClient;

  /// Generation runs a local LLM with up to one repair attempt, each bounded
  /// by the backend's 120 s timeout, before the deterministic fallback
  /// (ARCHITECTURE.md §5.3); the client waits longer than that worst case.
  static const Duration generateTimeout = Duration(seconds: 300);

  final ApiClient _api;

  /// The report for [playerId]: a cached one when the backend has it, or a
  /// new one. The backend answers 200 even when the LLM is down. When
  /// [cancel] completes, the request is aborted and this throws a
  /// `RequestCancelledException`.
  Future<ScoutingReport> generate(
    int playerId, {
    bool forceRegenerate = false,
    Future<void>? cancel,
  }) async {
    final json = await _api.postJson(
      '/reports/generate',
      {
        'player_id': playerId,
        'report_type': 'scouting',
        'force_regenerate': forceRegenerate,
      },
      timeout: generateTimeout,
      cancel: cancel,
    );
    return ReportDto.fromJson(json).toDomain();
  }

  /// The newest stored report for [playerId] in the active model run, or
  /// `null` when there is none. Unlike [generate], this never starts a
  /// generation.
  Future<ScoutingReport?> latestFor(int playerId) async {
    final json = await _api.getJson(
      '/reports',
      query: {'player_id': '$playerId', 'limit': '1'},
    );
    return switch (json) {
      {'items': []} => null,
      {'items': [final Map<String, Object?> newest, ...]} => ReportDto.fromJson(
        newest,
      ).toDomain(),
      _ => throw FormatException('Invalid report list', json),
    };
  }

  /// A stored report by its id.
  Future<ScoutingReport> getReport(int reportId) async =>
      ReportDto.fromJson(await _api.getJson('/reports/$reportId')).toDomain();
}
