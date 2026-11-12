/// A generated scouting report.
library;

/// A report for one player. [html] is the backend's escaped HTML: three
/// `<p>` paragraphs with `<strong>` and `<em>` (ARCHITECTURE.md §5.3).
class ScoutingReport {
  const ScoutingReport({
    required this.id,
    required this.playerId,
    required this.html,
    required this.writtenByModel,
    required this.createdAt,
    required this.modelRunId,
    this.playerName,
    this.llmModel,
  });

  final int id;
  final int playerId;
  final String html;

  /// `true` when the language model wrote the text, `false` when the
  /// deterministic renderer produced it (ADR-019).
  final bool writtenByModel;
  final DateTime createdAt;
  final String modelRunId;
  final String? playerName;
  final String? llmModel;
}
