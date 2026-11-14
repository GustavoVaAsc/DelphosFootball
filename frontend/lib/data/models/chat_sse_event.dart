/// SSE frame parser and data holder for `POST /chat` streamed responses.
library;

import 'dart:convert';

/// One parsed server-sent event from the conversational scouting endpoint.
final class ChatSseEvent {
  const ChatSseEvent({required this.event, required this.data});

  final String event;
  final Map<String, Object?> data;

  /// Parses one raw SSE frame block (`event: ...` / `data: ...`), or `null`.
  static ChatSseEvent? tryParseBlock(String block) {
    final lines = block.split('\n');
    var event = 'message';
    final dataLines = <String>[];
    for (final raw in lines) {
      if (raw.isEmpty || raw.startsWith(':')) continue;
      if (raw.startsWith('event:')) {
        event = raw.substring(6).trim();
      } else if (raw.startsWith('data:')) {
        dataLines.add(raw.substring(5).trimLeft());
      }
    }
    if (dataLines.isEmpty) return null;
    final payload = dataLines.join('\n');
    final decoded = jsonDecode(payload);
    if (decoded is! Map<String, Object?>) {
      throw const FormatException('Invalid SSE JSON payload');
    }
    return ChatSseEvent(event: event, data: decoded);
  }
}
