/// A message row of `GET /chat/sessions/{id}` (`ChatMessage` in
/// `backend/src/delphos_backend/schemas/chat.py`).
library;

import '../../domain/models/chat_history_message.dart';
import '../../domain/models/chat_referenced_player.dart';
import 'chat_referenced_player_dto.dart';
import 'json_fields.dart';

/// One stored message, as the backend sends it.
class ChatMessageDto {
  const ChatMessageDto({
    required this.role,
    required this.content,
    required this.createdAt,
    this.players = const [],
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
        players: ChatReferencedPlayerDto.parseList(json['players']),
      ),
    _ => throw FormatException('Invalid chat message', json),
  };

  ChatHistoryMessage toDomain() => ChatHistoryMessage(
    role: role,
    content: content,
    createdAt: createdAt,
    players: players,
  );

  final String role;
  final String content;
  final DateTime createdAt;
  final List<ChatReferencedPlayer> players;
}
