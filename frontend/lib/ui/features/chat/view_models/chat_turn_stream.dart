/// One chat turn as a stream of snapshots: the turn after each server-sent
/// event, then the turn finished. Errors from the request propagate to the
/// caller, which owns how a failed turn looks.
library;

import 'dart:async';

import '../../../../data/repositories/chat_repository.dart';
import '../../../../domain/models/chat_turn.dart';
import 'chat_turn_events.dart';

/// Streams [turn] through `/chat`. [onSession] receives a new session id.
Stream<ChatTurn> streamChatTurn(
  ChatRepository repository,
  ChatTurn turn, {
  required String? sessionId,
  required Future<void> cancel,
  required void Function(String sessionId) onSession,
}) async* {
  var current = turn;
  var cancelled = false;
  unawaited(cancel.whenComplete(() => cancelled = true));
  await for (final event in repository.streamTurn(
    message: turn.userMessage,
    sessionId: sessionId,
    cancel: cancel,
  )) {
    // A cancelled turn ignores what was already buffered: no event of it
    // may change anything (not even the session id).
    if (cancelled) return;
    current = applyChatEvent(current, event, onSession: onSession);
    yield current;
  }
  if (current.isStreaming) yield current.finished();
}
