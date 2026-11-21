/// Compact metadata of a player referenced by a PitIA response.
library;

import 'valuation_status.dart';

/// Hydrated outside the LLM prompt so the chat bubble shows portraits, crests,
/// flags and league logos with a direct link to the player's dossier.
final class ChatReferencedPlayer {
  const ChatReferencedPlayer({
    required this.id,
    required this.name,
    this.position,
    this.subPosition,
    this.country,
    this.clubName,
    this.clubLogoUrl,
    this.leagueId,
    this.imageUrl,
    this.marketValueEur,
    this.fairValueEur,
    this.valuationStatus,
  });

  final int id;
  final String name;
  final String? position;
  final String? subPosition;
  final String? country;
  final String? clubName;
  final String? clubLogoUrl;
  final String? leagueId;
  final String? imageUrl;
  final double? marketValueEur;
  final double? fairValueEur;
  final ValuationStatus? valuationStatus;
}
