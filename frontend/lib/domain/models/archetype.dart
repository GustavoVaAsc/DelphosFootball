/// One K-Means archetype's summary.
library;

/// An archetype card of view 3 (DESIGN.md §4, Arquetipos Tácticos). Its
/// names come from the labels by [clusterId].
class Archetype {
  const Archetype({
    required this.clusterId,
    required this.playerCount,
    required this.avgMarketValueEur,
    required this.avgMinutes,
    required this.avgGoals,
    required this.avgAssists,
  });

  final int clusterId;
  final int playerCount;
  final double avgMarketValueEur;
  final double avgMinutes;
  final double avgGoals;
  final double avgAssists;
}
