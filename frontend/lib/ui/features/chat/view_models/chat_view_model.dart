/// State and SSE orchestration for the conversational scouting assistant.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../../../data/models/chat_sse_event.dart';
import '../../../../data/repositories/chat_repository.dart';
import '../../../../data/services/api_exception.dart';
import '../../../../data/services/api_network_exception.dart';
import '../../../../data/services/request_cancelled_exception.dart';
import '../../../../domain/models/chat_turn.dart';
import 'chat_intro_gate.dart';
import 'chat_turn_events.dart';

/// Drives `/chat`: capabilities pop-up visibility and SSE turn streaming.
class ChatViewModel extends ChangeNotifier {
  ChatViewModel({required this._repository})
    : _isCapabilitiesOpen = ChatIntroGate.takeFirstVisit();

  final ChatRepository _repository;

  final List<ChatTurn> _turns = [];
  String? _sessionId;
  bool _isBusy = false;
  bool _isCapabilitiesOpen;
  bool _disposed = false;
  Completer<void>? _activeCancel;

  List<ChatTurn> get turns => List.unmodifiable(_turns);
  String? get sessionId => _sessionId;
  bool get isBusy => _isBusy;
  bool get isCapabilitiesOpen => _isCapabilitiesOpen;

  void openCapabilities() {
    if (_isCapabilitiesOpen) return;
    _isCapabilitiesOpen = true;
    notifyListeners();
  }

  void closeCapabilities() {
    if (!_isCapabilitiesOpen) return;
    _isCapabilitiesOpen = false;
    notifyListeners();
  }

  void clearConversation() {
    _cancelActive();
    _turns.clear();
    _sessionId = null;
    _isBusy = false;
    notifyListeners();
  }

  /// Whether the last turn failed and can be sent again.
  bool get canRetry =>
      !_isBusy && _turns.isNotEmpty && _turns.last.errorMessage != null;

  /// Drops the failed last turn and sends its question again.
  Future<void> retryLastTurn() {
    if (!canRetry) return Future.value();
    final text = _turns.removeLast().userMessage;
    return sendMessage(text);
  }

  Future<void> sendMessage(String rawText) async {
    final text = rawText.trim();
    if (text.isEmpty || _isBusy) return;
    _isCapabilitiesOpen = false;
    _isBusy = true;
    final turnIndex = _turns.length;
    _turns.add(ChatTurn(userMessage: text, isStreaming: true));
    final cancel = Completer<void>();
    _activeCancel = cancel;
    notifyListeners();

    try {
      await for (final event in _repository.streamTurn(
        message: text,
        sessionId: _sessionId,
        cancel: cancel.future,
      )) {
        if (_disposed || cancel.isCompleted) return;
        _applyEvent(turnIndex, event);
      }
      if (!_disposed && _turns[turnIndex].isStreaming) {
        _turns[turnIndex] = _turns[turnIndex].copyWith(isStreaming: false);
      }
    } on RequestCancelledException {
      return;
    } on ApiException catch (error) {
      _failTurn(turnIndex, chatApiErrorMessage(error));
    } on ApiNetworkException {
      _failTurn(
        turnIndex,
        'No se pudo conectar con el servidor. Revisa tu conexión e inténtalo '
        'de nuevo.',
      );
    } on FormatException {
      _failTurn(
        turnIndex,
        'La respuesta de PitIA llegó incompleta. Inténtalo de nuevo.',
      );
    } finally {
      if (identical(_activeCancel, cancel)) _activeCancel = null;
      _isBusy = false;
      if (!_disposed) notifyListeners();
    }
  }

  void _applyEvent(int index, ChatSseEvent event) {
    _turns[index] = applyChatEvent(
      _turns[index],
      event,
      onSession: (id) => _sessionId = id,
    );
    notifyListeners();
  }

  void _failTurn(int index, String message) {
    if (_disposed) return;
    _turns[index] = _turns[index].copyWith(
      errorMessage: message,
      isStreaming: false,
    );
  }

  void _cancelActive() {
    final cancel = _activeCancel;
    if (cancel != null && !cancel.isCompleted) cancel.complete();
    _activeCancel = null;
  }

  @override
  void dispose() {
    _disposed = true;
    _cancelActive();
    super.dispose();
  }
}
