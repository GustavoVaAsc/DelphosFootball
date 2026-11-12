/// A target player's replacement candidates.
library;

import 'replacement.dart';

/// Up to three candidates, never padded. With fewer than three,
/// [shortfallReason] carries the published code (label it in the UI).
class ReplacementSet {
  const ReplacementSet({
    required this.targetPlayerId,
    required this.targetName,
    required this.season,
    required this.isEliteAsset,
    required this.targetMarketValueEur,
    required this.qualifyingCount,
    required this.candidates,
    required this.modelRunId,
    this.shortfallReason,
  });

  final int targetPlayerId;
  final String targetName;
  final int season;
  final bool isEliteAsset;
  final double targetMarketValueEur;
  final int qualifyingCount;
  final List<Replacement> candidates;
  final String modelRunId;
  final String? shortfallReason;
}
