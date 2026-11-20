/// The conversation on show and how it changes other than by streaming a
/// turn: clearing it, switching to a saved session, and the bookkeeping that
/// cancels a turn in flight when either happens. `ChatViewModel` adds the
/// streaming of a new turn on top.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../../../data/repositories/chat_repository.dart';
import '../../../../domain/models/chat_session_history.dart';
import '../../../../domain/models/chat_turn.dart';
import 'chat_capabilities_state.dart';
import 'chat_history_turns.dart';
import 'chat_sessions_view_model.dart';

/// Turns, session id and busy flag of the chat, plus session switching.
abstract class ChatConversation extends ChangeNotifier
    with ChatCapabilitiesState {
  ChatConversation({required this.repository});

  @protected
  final ChatRepository repository;

  /// The "Conversaciones" menu.
  late final ChatSessionsViewModel sessions = ChatSessionsViewModel(
    repository: repository,
  );

  @protected
  final List<ChatTurn> turnList = [];
  String? _sessionId;
  int? _shownMessages;
  bool _isBusy = false;
  bool _disposed = false;
  Completer<void>? _activeCancel;

  List<ChatTurn> get turns => List.unmodifiable(turnList);
  String? get sessionId => _sessionId;

  @protected
  set sessionId(String? id) => _sessionId = id;

  bool get isBusy => _isBusy;

  @protected
  bool get isDisposed => _disposed;

  /// Whether a saved session is being loaded into the turns.
  bool get isRestoring => sessions.isRestoring;

  /// Whether the last saved session could not be loaded; the turns are still
  /// the ones from before.
  bool get restoreFailed => sessions.restoreFailed;

  /// How many messages a restored session shows when it has more than the
  /// backend sent (only the latest), or `null` when it is whole.
  int? get shownMessages => _shownMessages;

  /// Marks a turn as running and returns the signal that cancels it.
  @protected
  Completer<void> beginTurn() {
    _isBusy = true;
    return _activeCancel = Completer<void>();
  }

  /// Ends [cancel]'s turn. A turn that was superseded (cleared, replaced by
  /// a session) leaves the busy flag to whoever superseded it.
  @protected
  void endTurn(Completer<void> cancel) {
    if (identical(_activeCancel, cancel)) {
      _activeCancel = null;
      _isBusy = false;
    }
    if (!_disposed) notifyListeners();
  }

  /// Cancels the turn in flight. With [interrupt], the turn stays on screen
  /// (a session is about to load and may fail), so it stops spinning: it
  /// fails with a short message, its steps settle, and it can be retried.
  void _cancelActive({bool interrupt = false}) {
    final cancel = _activeCancel;
    if (interrupt && cancel != null && turnList.isNotEmpty) {
      final last = turnList.last;
      if (last.isStreaming) {
        turnList[turnList.length - 1] = last.failed(
          'Se interrumpió la respuesta.',
        );
      }
    }
    if (cancel != null && !cancel.isCompleted) cancel.complete();
    _activeCancel = null;
    _isBusy = false;
  }

  void clearConversation() {
    _cancelActive();
    sessions.reset();
    turnList.clear();
    _sessionId = null;
    _shownMessages = null;
    notifyListeners();
  }

  /// Shows the saved session [id] as completed turns and continues it with
  /// the next message. A failure leaves the conversation as it was and sets
  /// [restoreFailed]; [retryRestore] tries again.
  Future<void> openSession(String id) async {
    if (id == _sessionId && !isRestoring && !restoreFailed) {
      sessions.close();
      return;
    }
    _cancelActive(interrupt: true);
    _apply(await sessions.restore(id));
  }

  /// Loads the session that failed to open again.
  Future<void> retryRestore() async {
    if (!restoreFailed) return;
    _cancelActive(interrupt: true);
    _apply(await sessions.retryRestore());
  }

  void _apply(ChatSessionHistory? history) {
    if (_disposed || history == null) return;
    turnList
      ..clear()
      ..addAll(chatTurnsFromHistory(history));
    _sessionId = history.sessionId;
    _shownMessages = history.total > history.messages.length
        ? history.messages.length
        : null;
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _cancelActive();
    sessions.dispose();
    super.dispose();
  }
}
