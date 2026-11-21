/// One stored message of a saved conversation.
library;

import 'chat_referenced_player.dart';

/// A question (`user`) or an answer (`assistant`) as persisted by the backend.
class ChatHistoryMessage {
  const ChatHistoryMessage({
    required this.role,
    required this.content,
    required this.createdAt,
    this.players = const [],
  });

  /// `user` or `assistant`.
  final String role;
  final String content;
  final DateTime createdAt;
  final List<ChatReferencedPlayer> players;

  bool get isUser => role == 'user';
  bool get isAssistant => role == 'assistant';
}
