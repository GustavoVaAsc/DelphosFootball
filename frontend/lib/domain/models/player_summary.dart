/// A player as the explorer table lists it.
library;

import 'valuation_status.dart';

/// One row of the market table. Every field the backend may omit is
/// nullable; the UI omits what is missing instead of inventing it.
class PlayerSummary {
  const PlayerSummary({
    required this.id,
    required this.name,
    required this.position,
    this.subPosition,
    this.country,
    this.clubName,
    this.clubLogoUrl,
    this.imageUrl,
    this.marketValueEur,
    this.fairValueEur,
    this.age,
    this.valuationStatus,
    this.clusterId,
  });

  final int id;
  final String name;

  /// The dataset's English position key ("Attack"); label it in the UI.
  final String position;
  final String? subPosition;

  /// The dataset's English country of citizenship; label it in the UI.
  final String? country;
  final String? clubName;
  final String? clubLogoUrl;
  final String? imageUrl;
  final double? marketValueEur;

  /// The model's estimate, once the backend sends it in the list.
  final double? fairValueEur;

  /// The season age, once the backend sends it in the list.
  final double? age;
  final ValuationStatus? valuationStatus;
  final int? clusterId;
}
