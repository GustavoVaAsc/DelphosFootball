/// Renders one question-and-answer turn as user and PitIA chat bubbles.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/chat_turn.dart';
import 'chat_assistant_bubble.dart';
import 'chat_user_bubble.dart';

/// Pairs the right-aligned user prompt bubble with PitIA's left-aligned bubble.
class ChatTurnCard extends StatelessWidget {
  const ChatTurnCard({super.key, required this.turn, this.onRetry});

  final ChatTurn turn;

  /// Resends the turn; offered only while the turn shows an error.
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final hasAssistant =
        turn.steps.isNotEmpty ||
        turn.isStreaming ||
        turn.assistantMessage != null ||
        turn.errorMessage != null;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      spacing: 10,
      children: [
        ChatUserBubble(message: turn.userMessage),
        if (hasAssistant) ChatAssistantBubble(turn: turn, onRetry: onRetry),
      ],
    );
  }
}
