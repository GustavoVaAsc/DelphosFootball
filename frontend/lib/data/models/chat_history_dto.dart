/// The body of `GET /chat/sessions/{id}` (`ChatHistoryResponse` in
/// `backend/src/delphos_backend/schemas/chat.py`).
library;

import '../../domain/models/chat_session_history.dart';
import 'chat_message_dto.dart';
import 'json_fields.dart';

/// One page of a session's stored messages.
class ChatHistoryDto {
  const ChatHistoryDto({
    required this.sessionId,
    required this.items,
    required this.total,
    this.title,
  });

  factory ChatHistoryDto.fromJson(Map<String, Object?> json) => switch (json) {
    {'session_id': String sessionId, 'total': int total} => ChatHistoryDto(
      sessionId: sessionId,
      title: optionalString(json, 'title'),
      items: objectList(json, 'items', ChatMessageDto.fromJson),
      total: total,
    ),
    _ => throw FormatException('Invalid chat history', json),
  };

  ChatSessionHistory toDomain() => ChatSessionHistory(
    sessionId: sessionId,
    title: title,
    messages: [for (final item in items) item.toDomain()],
    total: total,
  );

  final String sessionId;
  final String? title;
  final List<ChatMessageDto> items;
  final int total;
}
