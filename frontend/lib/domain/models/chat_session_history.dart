/// The stored messages of one saved conversation.
library;

import 'chat_history_message.dart';

/// A session's messages in chronological order. Tool steps are not stored,
/// so a restored conversation has only questions and answers.
class ChatSessionHistory {
  const ChatSessionHistory({
    required this.sessionId,
    required this.messages,
    required this.total,
    this.title,
  });

  final String sessionId;
  final String? title;
  final List<ChatHistoryMessage> messages;

  /// How many messages the session has; more than [messages] when the
  /// backend sent only a page.
  final int total;
}
