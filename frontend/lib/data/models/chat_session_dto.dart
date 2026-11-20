/// A session row of `GET /chat/sessions` (`ChatSession` in
/// `backend/src/delphos_backend/schemas/chat.py`).
library;

import '../../domain/models/chat_session_summary.dart';
import 'json_fields.dart';

/// One saved conversation, as the backend sends it.
class ChatSessionDto {
  const ChatSessionDto({
    required this.id,
    required this.createdAt,
    required this.updatedAt,
    this.title,
  });

  factory ChatSessionDto.fromJson(Map<String, Object?> json) => switch (json) {
    {
      'id': String id,
      'created_at': String createdAt,
      'updated_at': String updatedAt,
    } =>
      ChatSessionDto(
        id: id,
        title: optionalString(json, 'title'),
        createdAt: parseIsoDate('created_at', createdAt),
        updatedAt: parseIsoDate('updated_at', updatedAt),
      ),
    _ => throw FormatException('Invalid chat session', json),
  };

  ChatSessionSummary toDomain() => ChatSessionSummary(
    id: id,
    title: title,
    createdAt: createdAt,
    updatedAt: updatedAt,
  );

  final String id;
  final String? title;
  final DateTime createdAt;
  final DateTime updatedAt;
}
