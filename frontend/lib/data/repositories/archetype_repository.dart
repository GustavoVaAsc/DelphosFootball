/// Archetype data for view 3: the `/clusters` endpoint of the backend.
library;

import '../../domain/models/archetype_overview.dart';
import '../models/cluster_list_dto.dart';
import '../services/api_client.dart';

/// Reads the K-Means archetypes of the active season.
class ArchetypeRepository {
  ArchetypeRepository({required ApiClient apiClient}) : _api = apiClient;

  final ApiClient _api;

  /// Every archetype with its averages and player count.
  Future<ArchetypeOverview> getOverview() async =>
      ClusterListDto.fromJson(await _api.getJson('/clusters')).toDomain();
}
