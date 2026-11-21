/// One question-and-answer turn in the scouting assistant conversation.
library;

import 'chat_referenced_player.dart';
import 'chat_tool_step.dart';

/// Immutable snapshot of one user prompt and the agent's progress/answer.
final class ChatTurn {
  const ChatTurn({
    required this.userMessage,
    this.steps = const [],
    this.assistantMessage,
    this.players = const [],
    this.errorMessage,
    this.isStreaming = false,
  });

  final String userMessage;
  final List<ChatToolStep> steps;
  final String? assistantMessage;
  final List<ChatReferencedPlayer> players;
  final String? errorMessage;
  final bool isStreaming;

  ChatTurn copyWith({
    List<ChatToolStep>? steps,
    String? assistantMessage,
    List<ChatReferencedPlayer>? players,
    String? errorMessage,
    bool? isStreaming,
  }) => ChatTurn(
    userMessage: userMessage,
    steps: steps ?? this.steps,
    assistantMessage: assistantMessage ?? this.assistantMessage,
    players: players ?? this.players,
    errorMessage: errorMessage ?? this.errorMessage,
    isStreaming: isStreaming ?? this.isStreaming,
  );

  /// This turn once its stream ended: no step still runs.
  ChatTurn finished() => copyWith(
    steps: [for (final step in steps) step.settled(failed: false)],
    isStreaming: false,
  );

  /// This turn once it failed with [message]: running steps failed too.
  ChatTurn failed(String message) => copyWith(
    steps: [for (final step in steps) step.settled(failed: true)],
    errorMessage: message,
    isStreaming: false,
  );
}
