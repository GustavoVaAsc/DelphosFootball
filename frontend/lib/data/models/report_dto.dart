/// The body of `POST /reports/generate` and `GET /reports/{id}`
/// (`ReportResponse` in `backend/src/delphos_backend/schemas/reports.py`).
library;

import 'json_fields.dart';
import '../../domain/models/scouting_report.dart';

/// A persisted scouting report, as the backend sends it.
class ReportDto {
  const ReportDto({
    required this.id,
    required this.playerId,
    required this.modelRunId,
    required this.content,
    required this.source,
    required this.createdAt,
    this.playerName,
    this.llmModel,
  });

  factory ReportDto.fromJson(Map<String, Object?> json) => switch (json) {
    {
      'id': int id,
      'player_id': int playerId,
      'model_run_id': String modelRunId,
      'content': String content,
      'source': String source,
      'created_at': String createdAt,
    } =>
      ReportDto(
        id: id,
        playerId: playerId,
        modelRunId: modelRunId,
        content: content,
        source: source,
        createdAt: parseIsoDate('created_at', createdAt),
        playerName: optionalString(json, 'player_name'),
        llmModel: optionalString(json, 'llm_model'),
      ),
    _ => throw FormatException('Invalid report', json),
  };

  ScoutingReport toDomain() => ScoutingReport(
    id: id,
    playerId: playerId,
    html: content,
    writtenByModel: source == 'llm',
    createdAt: createdAt,
    modelRunId: modelRunId,
    playerName: playerName,
    llmModel: llmModel,
  );

  final int id;
  final int playerId;
  final String modelRunId;

  /// Three `<p>` paragraphs of escaped HTML (ARCHITECTURE.md §5.3).
  final String content;

  /// `llm` or `deterministic`.
  final String source;
  final DateTime createdAt;
  final String? playerName;
  final String? llmModel;
}
