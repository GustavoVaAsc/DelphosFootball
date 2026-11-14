/// One question-and-answer turn in the scouting assistant conversation.
library;

import 'chat_tool_step.dart';

/// Immutable snapshot of one user prompt and the agent's progress/answer.
final class ChatTurn {
  const ChatTurn({
    required this.userMessage,
    this.steps = const [],
    this.assistantMessage,
    this.errorMessage,
    this.isStreaming = false,
  });

  final String userMessage;
  final List<ChatToolStep> steps;
  final String? assistantMessage;
  final String? errorMessage;
  final bool isStreaming;

  ChatTurn copyWith({
    List<ChatToolStep>? steps,
    String? assistantMessage,
    String? errorMessage,
    bool? isStreaming,
  }) => ChatTurn(
    userMessage: userMessage,
    steps: steps ?? this.steps,
    assistantMessage: assistantMessage ?? this.assistantMessage,
    errorMessage: errorMessage ?? this.errorMessage,
    isStreaming: isStreaming ?? this.isStreaming,
  );
}
