/// The body of `GET /players/{id}/replacements`
/// (`TargetReplacementsResponse` in
/// `backend/src/delphos_backend/schemas/replacements.py`).
library;

import 'json_fields.dart';
import 'replacement_item_dto.dart';
import '../../domain/models/replacement_set.dart';

/// A target player's replacement set, as the backend sends it.
class ReplacementsDto {
  const ReplacementsDto({
    required this.targetPlayerId,
    required this.targetName,
    required this.modelRunId,
    required this.season,
    required this.isEliteAsset,
    required this.targetMarketValueEur,
    required this.qualifyingCount,
    required this.replacements,
    this.shortfallReason,
  });

  factory ReplacementsDto.fromJson(Map<String, Object?> json) => switch (json) {
    {
      'target_player_id': int targetPlayerId,
      'target_name': String targetName,
      'model_run_id': String modelRunId,
      'season': int season,
      'is_elite_asset': bool isEliteAsset,
      'target_market_value_eur': num targetMarketValueEur,
      'qualifying_count': int qualifyingCount,
    } =>
      ReplacementsDto(
        targetPlayerId: targetPlayerId,
        targetName: targetName,
        modelRunId: modelRunId,
        season: season,
        isEliteAsset: isEliteAsset,
        targetMarketValueEur: targetMarketValueEur.toDouble(),
        qualifyingCount: qualifyingCount,
        shortfallReason: optionalString(json, 'shortfall_reason'),
        replacements: json['replacements'] == null
            ? const []
            : objectList(json, 'replacements', ReplacementItemDto.fromJson),
      ),
    _ => throw FormatException('Invalid replacements', json),
  };

  ReplacementSet toDomain() => ReplacementSet(
    targetPlayerId: targetPlayerId,
    targetName: targetName,
    season: season,
    isEliteAsset: isEliteAsset,
    targetMarketValueEur: targetMarketValueEur,
    qualifyingCount: qualifyingCount,
    candidates: [for (final item in replacements) item.toDomain()],
    modelRunId: modelRunId,
    shortfallReason: shortfallReason,
  );

  final int targetPlayerId;
  final String targetName;
  final String modelRunId;
  final int season;
  final bool isEliteAsset;
  final double targetMarketValueEur;
  final int qualifyingCount;
  final String? shortfallReason;
  final List<ReplacementItemDto> replacements;
}
