/// A player's active-season figures.
library;

/// The season grid of the dossier (DESIGN.md §4, Season). Counts arrive as
/// numbers from the backend and stay doubles; the formatters round them.
class SeasonStats {
  const SeasonStats({
    required this.season,
    required this.asOfDate,
    required this.leagueId,
    required this.minutes,
    required this.apps,
    required this.starts,
    required this.goals,
    required this.assists,
    required this.yellowCards,
    required this.redCards,
    required this.starterRatio,
    required this.winRate,
    required this.cleanSheetRate,
    required this.goalsConcededPerMatch,
    required this.age,
    this.leaguePosition,
  });

  /// The start year of the season (2025 is "2025/26").
  final int season;

  /// The date the season figures were measured.
  final DateTime asOfDate;

  /// The Transfermarkt league id; label it in the UI.
  final String leagueId;
  final double minutes;
  final double apps;
  final double starts;
  final double goals;
  final double assists;
  final double yellowCards;
  final double redCards;

  /// Shares in 0..1; a value outside that range prints "N/D".
  final double starterRatio;
  final double winRate;
  final double cleanSheetRate;
  final double goalsConcededPerMatch;
  final double age;
  final double? leaguePosition;
}
