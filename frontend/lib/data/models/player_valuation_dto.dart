/// The body of `GET /players/{id}/valuation` (`PlayerValuationResponse` in
/// `backend/src/delphos_backend/schemas/players.py`).
library;

import '../../domain/models/player_valuation.dart';
import '../../domain/models/valuation_status.dart';

/// A player's model valuation, as the backend sends it.
class PlayerValuationDto {
  const PlayerValuationDto({
    required this.playerId,
    required this.modelRunId,
    required this.season,
    required this.marketValueEur,
    required this.fairValueEur,
    required this.valuationStatus,
    required this.isUndervalued,
    required this.rfUndervaluedProb,
    required this.rfUndervaluedPred,
    required this.dtUndervaluedPred,
  });

  factory PlayerValuationDto.fromJson(Map<String, Object?> json) =>
      switch (json) {
        {
          'player_id': int playerId,
          'model_run_id': String modelRunId,
          'season': int season,
          'market_value_eur': num marketValueEur,
          'fair_value_eur': num fairValueEur,
          'valuation_status': String valuationStatus,
          'is_undervalued': bool isUndervalued,
          'rf_undervalued_prob': num rfUndervaluedProb,
          'rf_undervalued_pred': bool rfUndervaluedPred,
          'dt_undervalued_pred': bool dtUndervaluedPred,
        } =>
          PlayerValuationDto(
            playerId: playerId,
            modelRunId: modelRunId,
            season: season,
            marketValueEur: marketValueEur.toDouble(),
            fairValueEur: fairValueEur.toDouble(),
            valuationStatus: valuationStatus,
            isUndervalued: isUndervalued,
            rfUndervaluedProb: rfUndervaluedProb.toDouble(),
            rfUndervaluedPred: rfUndervaluedPred,
            dtUndervaluedPred: dtUndervaluedPred,
          ),
        _ => throw FormatException('Invalid player valuation', json),
      };

  /// Throws a [FormatException] for a status the app does not know: the
  /// verdict is the one figure the dossier cannot show without.
  PlayerValuation toDomain() => PlayerValuation(
    playerId: playerId,
    season: season,
    marketValueEur: marketValueEur,
    fairValueEur: fairValueEur,
    status:
        ValuationStatus.fromApi(valuationStatus) ??
        (throw FormatException('Unknown valuation status', valuationStatus)),
    rfUndervaluedProb: rfUndervaluedProb,
    rfUndervaluedPred: rfUndervaluedPred,
    dtUndervaluedPred: dtUndervaluedPred,
    modelRunId: modelRunId,
  );

  final int playerId;
  final String modelRunId;
  final int season;
  final double marketValueEur;
  final double fairValueEur;
  final String valuationStatus;
  final bool isUndervalued;
  final double rfUndervaluedProb;
  final bool rfUndervaluedPred;
  final bool dtUndervaluedPred;
}
