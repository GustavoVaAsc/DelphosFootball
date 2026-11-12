/// The archetypes of the active season.
library;

import 'archetype.dart';

/// All archetypes, with the total the share bar divides by.
class ArchetypeOverview {
  const ArchetypeOverview({
    required this.season,
    required this.archetypes,
    required this.modelRunId,
    this.asOfDate,
  });

  final int season;
  final List<Archetype> archetypes;
  final String modelRunId;

  /// The latest `as_of_date` in the data ("datos al 5 jun 2026"), when the
  /// backend sends it.
  final DateTime? asOfDate;

  /// Players across all archetypes (the sidebar's "5.522 jugadores").
  int get totalPlayers =>
      archetypes.fold(0, (sum, archetype) => sum + archetype.playerCount);
}
