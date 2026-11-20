/// A saved conversation, as listed in the chat's "Conversaciones" menu.
library;

/// One row of the session list: its id, an optional title and its dates.
class ChatSessionSummary {
  const ChatSessionSummary({
    required this.id,
    required this.createdAt,
    required this.updatedAt,
    this.title,
  });

  final String id;

  /// The first question of the session; `null` until the backend sets it.
  final String? title;
  final DateTime createdAt;

  /// When the last message was stored; the list is ordered by it.
  final DateTime updatedAt;
}
