/// Repository for conversational scouting turns (`POST /chat`) and the saved
/// sessions (`GET /chat/sessions`, `GET /chat/sessions/{id}`).
library;

import 'dart:math' as math;

import '../../domain/models/chat_session_history.dart';
import '../../domain/models/chat_session_summary.dart';
import '../models/chat_history_dto.dart';
import '../models/chat_session_list_dto.dart';
import '../models/chat_sse_event.dart';
import '../services/api_client.dart';

/// Streams tool-call progress and final answers from `/chat`, and reads the
/// saved conversations.
class ChatRepository {
  ChatRepository({required ApiClient apiClient}) : _api = apiClient;

  static const Duration turnTimeout = Duration(seconds: 180);

  /// The most messages one history request returns (the backend's cap).
  static const int historyPageSize = 200;

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

  /// The saved conversations, most recently active first.
  Future<List<ChatSessionSummary>> listSessions() async {
    final json = await _api.getJson('/chat/sessions');
    return ChatSessionListDto.fromJson(json).toDomain();
  }

  /// The stored messages of [sessionId] in order. A first request for one
  /// message reads the total; a session longer than [historyPageSize] then
  /// yields only its latest messages ([ChatSessionHistory.total] tells).
  Future<ChatSessionHistory> getSession(String sessionId) async {
    final path = '/chat/sessions/${Uri.encodeComponent(sessionId)}';
    final probe = ChatHistoryDto.fromJson(
      await _api.getJson(path, query: {'limit': '1'}),
    );
    final offset = math.max(0, probe.total - historyPageSize);
    final latest = ChatHistoryDto.fromJson(
      await _api.getJson(
        path,
        query: {'limit': '$historyPageSize', 'offset': '$offset'},
      ),
    );
    return latest.toDomain();
  }
}
