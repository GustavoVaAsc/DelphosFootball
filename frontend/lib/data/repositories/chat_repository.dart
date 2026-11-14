/// Repository for conversational scouting turns (`POST /chat`).
library;

import '../models/chat_sse_event.dart';
import '../services/api_client.dart';

/// Streams tool-call progress and final answers from `/chat`.
class ChatRepository {
  ChatRepository({required ApiClient apiClient}) : _api = apiClient;

  static const Duration turnTimeout = Duration(seconds: 180);

  final ApiClient _api;

  /// Sends [message] to the assistant using SSE streaming (`stream: true`).
  Stream<ChatSseEvent> streamTurn({
    required String message,
    String? sessionId,
    Future<void>? cancel,
  }) async* {
    final chunks = _api.postEventStream(
      '/chat',
      {'message': message, 'session_id': ?sessionId, 'stream': true},
      timeout: turnTimeout,
      cancel: cancel,
    );
    var buffer = '';
    await for (final chunk in chunks) {
      buffer += chunk.replaceAll('\r\n', '\n').replaceAll('\r', '\n');
      while (true) {
        final split = buffer.indexOf('\n\n');
        if (split < 0) break;
        final block = buffer.substring(0, split).trim();
        buffer = buffer.substring(split + 2);
        if (block.isEmpty) continue;
        final event = ChatSseEvent.tryParseBlock(block);
        if (event != null) yield event;
      }
    }
    final trailing = buffer.trim();
    if (trailing.isNotEmpty) {
      final event = ChatSseEvent.tryParseBlock(trailing);
      if (event != null) yield event;
    }
  }
}
