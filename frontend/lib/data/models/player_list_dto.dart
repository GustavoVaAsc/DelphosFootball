/// The body of `GET /players` (`PlayerListResponse` in
/// `backend/src/delphos_backend/schemas/players.py`).
library;

import 'json_fields.dart';
import 'player_summary_dto.dart';
import '../../domain/models/player_page.dart';

/// One page of players.
class PlayerListDto {
  const PlayerListDto({
    required this.modelRunId,
    required this.items,
    required this.total,
    required this.page,
    required this.pageSize,
    required this.totalPages,
  });

  factory PlayerListDto.fromJson(Map<String, Object?> json) => switch (json) {
    {
      'model_run_id': String modelRunId,
      'total': int total,
      'page': int page,
      'page_size': int pageSize,
      'total_pages': int totalPages,
    } =>
      PlayerListDto(
        modelRunId: modelRunId,
        items: objectList(json, 'items', PlayerSummaryDto.fromJson),
        total: total,
        page: page,
        pageSize: pageSize,
        totalPages: totalPages,
      ),
    _ => throw FormatException('Invalid player list', json),
  };

  PlayerPage toDomain() => PlayerPage(
    players: [for (final item in items) item.toDomain()],
    total: total,
    page: page,
    pageSize: pageSize,
    totalPages: totalPages,
    modelRunId: modelRunId,
  );

  final String modelRunId;
  final List<PlayerSummaryDto> items;
  final int total;
  final int page;
  final int pageSize;
  final int totalPages;
}
