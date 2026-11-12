/// One page of the player list.
library;

import 'player_summary.dart';

/// A page of players with the totals the table footer needs.
class PlayerPage {
  const PlayerPage({
    required this.players,
    required this.total,
    required this.page,
    required this.pageSize,
    required this.totalPages,
    required this.modelRunId,
  });

  final List<PlayerSummary> players;

  /// Players matching the filters across all pages.
  final int total;

  /// The 1-based page number.
  final int page;
  final int pageSize;
  final int totalPages;

  /// The model run that produced the valuations on this page.
  final String modelRunId;
}
