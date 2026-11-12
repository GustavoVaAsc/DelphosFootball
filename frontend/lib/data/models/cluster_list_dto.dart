/// The body of `GET /clusters` (`ClusterListResponse` in
/// `backend/src/delphos_backend/schemas/clusters.py`).
library;

import 'cluster_dto.dart';
import 'json_fields.dart';
import '../../domain/models/archetype_overview.dart';

/// The archetype summaries of the active season.
class ClusterListDto {
  const ClusterListDto({
    required this.modelRunId,
    required this.season,
    required this.clusters,
    this.asOfDate,
  });

  factory ClusterListDto.fromJson(Map<String, Object?> json) => switch (json) {
    {'model_run_id': String modelRunId, 'season': int season} => ClusterListDto(
      modelRunId: modelRunId,
      season: season,
      clusters: objectList(json, 'clusters', ClusterDto.fromJson),
      asOfDate: switch (optionalString(json, 'as_of_date')) {
        final date? => parseIsoDate('as_of_date', date),
        null => null,
      },
    ),
    _ => throw FormatException('Invalid cluster list', json),
  };

  ArchetypeOverview toDomain() => ArchetypeOverview(
    season: season,
    archetypes: [for (final cluster in clusters) cluster.toDomain()],
    modelRunId: modelRunId,
    asOfDate: asOfDate,
  );

  final String modelRunId;
  final int season;
  final List<ClusterDto> clusters;

  /// The latest data date; optional until the backend sends it.
  final DateTime? asOfDate;
}
