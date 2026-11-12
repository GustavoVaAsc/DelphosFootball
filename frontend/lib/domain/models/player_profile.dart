/// A player's biography and active season, for the dossier.
library;

import 'season_stats.dart';

/// The dossier header and season grid. [season] is `null` for a player
/// without season statistics (DESIGN.md §7, "no-season").
class PlayerProfile {
  const PlayerProfile({
    required this.id,
    required this.name,
    required this.lastName,
    required this.dateOfBirth,
    required this.position,
    required this.transfermarktUrl,
    this.firstName,
    this.country,
    this.subPosition,
    this.foot,
    this.heightCm,
    this.clubName,
    this.clubLogoUrl,
    this.imageUrl,
    this.clusterId,
    this.season,
  });

  final int id;
  final String name;
  final String lastName;
  final DateTime dateOfBirth;
  final String position;
  final String transfermarktUrl;
  final String? firstName;
  final String? country;
  final String? subPosition;

  /// "right", "left" or "both"; label it in the UI.
  final String? foot;
  final int? heightCm;
  final String? clubName;
  final String? clubLogoUrl;
  final String? imageUrl;
  final int? clusterId;
  final SeasonStats? season;
}
