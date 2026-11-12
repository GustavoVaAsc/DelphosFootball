/// The model's valuation of one player.
library;

import 'valuation_status.dart';

/// Market price, the model's estimate, the verdict and the classifier check
/// (DESIGN.md §4, Valuation).
class PlayerValuation {
  const PlayerValuation({
    required this.playerId,
    required this.season,
    required this.marketValueEur,
    required this.fairValueEur,
    required this.status,
    required this.rfUndervaluedProb,
    required this.rfUndervaluedPred,
    required this.dtUndervaluedPred,
    required this.modelRunId,
  });

  final int playerId;
  final int season;
  final double marketValueEur;

  /// The model's estimate, shown as "Valor estimado".
  final double fairValueEur;

  /// The only verdict on screen.
  final ValuationStatus status;

  /// Random Forest probability of undervaluation, in 0..1.
  final double rfUndervaluedProb;
  final bool rfUndervaluedPred;
  final bool dtUndervaluedPred;
  final String modelRunId;
}
