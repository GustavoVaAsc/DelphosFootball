/// One intermediate consultation step performed by the scouting agent.
library;

/// A single natural-language step reported while resolving a chat turn.
final class ChatToolStep {
  const ChatToolStep({
    required this.stepTitle,
    required this.summary,
    this.isError = false,
  });

  /// Natural Spanish title describing the lookup step (never a function name).
  final String stepTitle;

  /// Human-readable Spanish summary returned for this step.
  final String summary;

  /// Whether this lookup reported a retryable error to the agent.
  final bool isError;
}
