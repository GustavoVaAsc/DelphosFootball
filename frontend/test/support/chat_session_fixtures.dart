// Backend-shaped JSON for the chat session endpoints: a `ChatSession` row
// and the `ChatHistoryResponse` of one session.

/// A session row of `GET /chat/sessions`.
Map<String, Object?> chatSessionJson(
  String id, {
  String? title,
  String createdAt = '2026-11-10T09:00:00Z',
  String updatedAt = '2026-11-10T09:05:00Z',
}) => {
  'id': id,
  'title': title,
  'created_at': createdAt,
  'updated_at': updatedAt,
};

/// A stored message of `GET /chat/sessions/{id}`.
Map<String, Object?> chatMessageJson(
  String role,
  String content, {
  int n = 0,
}) => {
  'id': '00000000-0000-4000-8000-${n.toString().padLeft(12, '0')}',
  'role': role,
  'content': content,
  'created_at': '2026-11-10T09:0$n:00Z',
};

/// `GET /chat/sessions/{id}` for [items], with [total] when it differs.
Map<String, Object?> chatHistoryJson(
  String id,
  List<Map<String, Object?>> items, {
  String? title,
  int? total,
  int offset = 0,
}) => {
  'session_id': id,
  'title': title,
  'items': items,
  'total': total ?? items.length,
  'limit': 200,
  'offset': offset,
};
