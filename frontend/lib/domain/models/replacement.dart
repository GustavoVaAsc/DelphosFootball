/// One replacement candidate for a target player.
library;

import 'valuation_status.dart';

/// A ranked candidate: similar on the pitch and at least 20% cheaper.
class Replacement {
  const Replacement({
    required this.rank,
    required this.playerId,
    required this.name,
    required this.position,
    required this.similarity,
    required this.marketValueEur,
    required this.savingsEur,
    required this.costRatio,
    required this.fairValueEur,
    required this.status,
    this.country,
    this.clubName,
    this.clubLogoUrl,
    this.imageUrl,
  });

  /// 1 to 3.
  final int rank;
  final int playerId;
  final String name;
  final String position;

  /// Normalised similarity in 0..1.
  final double similarity;
  final double marketValueEur;

  /// The target's price minus this candidate's price.
  final double savingsEur;

  /// This candidate's price over the target's.
  final double costRatio;
  final double fairValueEur;

  /// `null` when the backend sends a status the app does not know.
  final ValuationStatus? status;
  final String? country;
  final String? clubName;
  final String? clubLogoUrl;
  final String? imageUrl;
}
