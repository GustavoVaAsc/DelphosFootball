/// The states of the dossier's Resumen (DESIGN.md §4 and §7).
library;

/// Where the scouting report of the player on show stands.
enum ReportStatus {
  /// No player on show.
  idle,

  /// Looking for a stored report.
  checking,

  /// The player has no stored report yet.
  none,

  /// A generation is in flight.
  generating,

  /// A report is on show.
  ready,

  /// The lookup or the generation failed.
  error,
}
