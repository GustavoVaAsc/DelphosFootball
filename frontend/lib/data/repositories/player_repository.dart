/// Player data for the explorer, the dossier and the comparator: the
/// `/players` endpoints of the backend.
library;

import '../../domain/models/player_page.dart';
import '../../domain/models/player_profile.dart';
import '../../domain/models/player_query.dart';
import '../../domain/models/player_valuation.dart';
import '../../domain/models/replacement_set.dart';
import '../models/player_list_dto.dart';
import '../models/player_profile_dto.dart';
import '../models/player_valuation_dto.dart';
import '../models/replacements_dto.dart';
import '../services/api_client.dart';

/// Reads players from the backend and returns domain models.
///
/// Errors propagate unchanged: `ApiException` for a backend answer (a 404
/// for an unknown player), `ApiNetworkException` when there is none, and
/// `FormatException` when a body breaks the contract.
class PlayerRepository {
  PlayerRepository({required ApiClient apiClient}) : _api = apiClient;

  final ApiClient _api;

  /// One page of players matching [query]. Throws an [ArgumentError] for a
  /// page below 1 or a page size outside 1..100 instead of sending it.
  Future<PlayerPage> listPlayers(PlayerQuery query) async {
    if (query.page < 1) {
      throw ArgumentError.value(query.page, 'page', 'must be at least 1');
    }
    if (query.pageSize < 1 || query.pageSize > PlayerQuery.maxPageSize) {
      throw ArgumentError.value(
        query.pageSize,
        'pageSize',
        'must be between 1 and ${PlayerQuery.maxPageSize}',
      );
    }
    final name = query.name?.trim();
    final json = await _api.getJson(
      '/players',
      query: {
        if (name != null && name.isNotEmpty) 'name': name,
        'position': ?query.position,
        if (query.valuationStatus case final status?)
          'valuation_status': status.apiValue,
        if (query.clusterId case final clusterId?) 'cluster_id': '$clusterId',
        'page': '${query.page}',
        'page_size': '${query.pageSize}',
      },
    );
    return PlayerListDto.fromJson(json).toDomain();
  }

  /// The biography and active season of one player.
  Future<PlayerProfile> getProfile(int playerId) async =>
      PlayerProfileDto.fromJson(await _api.getJson('/players/$playerId'))
          .toDomain();

  /// The model's valuation of one player.
  Future<PlayerValuation> getValuation(int playerId) async =>
      PlayerValuationDto.fromJson(
        await _api.getJson('/players/$playerId/valuation'),
      ).toDomain();

  /// The published replacement candidates for one player.
  Future<ReplacementSet> getReplacements(int playerId) async =>
      ReplacementsDto.fromJson(
        await _api.getJson('/players/$playerId/replacements'),
      ).toDomain();
}
