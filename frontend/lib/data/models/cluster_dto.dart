/// One archetype of `GET /clusters` (`ClusterArchetype` in
/// `backend/src/delphos_backend/schemas/clusters.py`).
library;

import '../../domain/models/archetype.dart';

/// One K-Means archetype's summary, as the backend sends it.
///
/// The backend's English `name` is not parsed: the app names archetypes by
/// `cluster_id` with the approved Spanish copy (ADR-020).
class ClusterDto {
  const ClusterDto({
    required this.clusterId,
    required this.playerCount,
    required this.avgMarketValueEur,
    required this.avgMinutes,
    required this.avgGoals,
    required this.avgAssists,
  });

  factory ClusterDto.fromJson(Map<String, Object?> json) => switch (json) {
    {
      'cluster_id': int clusterId,
      'player_count': int playerCount,
      'avg_market_value_eur': num avgMarketValueEur,
      'avg_minutes': num avgMinutes,
      'avg_goals': num avgGoals,
      'avg_assists': num avgAssists,
    } =>
      ClusterDto(
        clusterId: clusterId,
        playerCount: playerCount,
        avgMarketValueEur: avgMarketValueEur.toDouble(),
        avgMinutes: avgMinutes.toDouble(),
        avgGoals: avgGoals.toDouble(),
        avgAssists: avgAssists.toDouble(),
      ),
    _ => throw FormatException('Invalid cluster', json),
  };

  Archetype toDomain() => Archetype(
    clusterId: clusterId,
    playerCount: playerCount,
    avgMarketValueEur: avgMarketValueEur,
    avgMinutes: avgMinutes,
    avgGoals: avgGoals,
    avgAssists: avgAssists,
  );

  final int clusterId;
  final int playerCount;
  final double avgMarketValueEur;
  final double avgMinutes;
  final double avgGoals;
  final double avgAssists;
}
