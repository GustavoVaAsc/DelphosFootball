/// A message row of `GET /chat/sessions/{id}` (`ChatMessage` in
/// `backend/src/delphos_backend/schemas/chat.py`).
library;

import '../../domain/models/chat_history_message.dart';
import 'json_fields.dart';

/// One stored message, as the backend sends it.
class ChatMessageDto {
  const ChatMessageDto({
    required this.role,
    required this.content,
    required this.createdAt,
  });

  factory ChatMessageDto.fromJson(Map<String, Object?> json) => switch (json) {
    {
      'role': String role,
      'content': String content,
      'created_at': String createdAt,
    } =>
      ChatMessageDto(
        role: role,
        content: content,
        createdAt: parseIsoDate('created_at', createdAt),
      ),
    _ => throw FormatException('Invalid chat message', json),
  };

  ChatHistoryMessage toDomain() =>
      ChatHistoryMessage(role: role, content: content, createdAt: createdAt);

  final String role;
  final String content;
  final DateTime createdAt;
}
