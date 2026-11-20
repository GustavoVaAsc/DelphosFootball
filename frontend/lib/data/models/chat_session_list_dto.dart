/// The body of `GET /chat/sessions` (`ChatSessionListResponse` in
/// `backend/src/delphos_backend/schemas/chat.py`).
library;

import '../../domain/models/chat_session_summary.dart';
import 'chat_session_dto.dart';
import 'json_fields.dart';

/// The saved conversations, newest first.
class ChatSessionListDto {
  const ChatSessionListDto({required this.items});

  factory ChatSessionListDto.fromJson(Map<String, Object?> json) =>
      ChatSessionListDto(
        items: objectList(json, 'items', ChatSessionDto.fromJson),
      );

  List<ChatSessionSummary> toDomain() => [
    for (final item in items) item.toDomain(),
  ];

  final List<ChatSessionDto> items;
}
