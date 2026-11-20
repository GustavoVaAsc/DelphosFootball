/// One intermediate consultation step performed by the scouting agent.
library;

/// Where a step stands: started and not yet answered, finished, or failed.
enum ChatStepState { running, done, failed }

/// A single natural-language step reported while resolving a chat turn.
final class ChatToolStep {
  const ChatToolStep({
    required this.stepTitle,
    required this.summary,
    this.id,
    this.state = ChatStepState.done,
  });

  /// The server's step number, which pairs a `tool` event with its
  /// `tool_start`; `null` from a backend that sends neither.
  final int? id;

  /// Natural Spanish sentence describing the lookup step (never a function
  /// name): the server's live description, or a generic title.
  final String stepTitle;

  /// Human-readable Spanish summary returned for this step; empty while the
  /// step runs.
  final String summary;

  final ChatStepState state;

  bool get isRunning => state == ChatStepState.running;

  /// Whether this lookup reported a retryable error to the agent.
  bool get isError => state == ChatStepState.failed;

  /// This step once its turn has ended without its own result: done, or
  /// failed when the turn failed. A step that already ended is unchanged.
  ChatToolStep settled({required bool failed}) => isRunning
      ? ChatToolStep(
          id: id,
          stepTitle: stepTitle,
          summary: summary,
          state: failed ? ChatStepState.failed : ChatStepState.done,
        )
      : this;
}
