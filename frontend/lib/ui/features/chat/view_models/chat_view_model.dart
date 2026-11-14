/// State and SSE orchestration for the conversational scouting assistant.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../../../data/models/chat_sse_event.dart';
import '../../../../data/repositories/chat_repository.dart';
import '../../../../data/services/api_exception.dart';
import '../../../../data/services/api_network_exception.dart';
import '../../../../data/services/request_cancelled_exception.dart';
import '../../../../domain/models/chat_tool_step.dart';
import '../../../../domain/models/chat_turn.dart';
import '../../../core/labels/chat_tool_labels.dart';

/// Drives `/chat`: capabilities pop-up visibility and SSE turn streaming.
class ChatViewModel extends ChangeNotifier {
  ChatViewModel({required this._repository});

  final ChatRepository _repository;

  final List<ChatTurn> _turns = [];
  String? _sessionId;
  bool _isBusy = false;
  bool _isCapabilitiesOpen = true;
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
      _failTurn(turnIndex, _mapApiError(error));
    } on ApiNetworkException {
      _failTurn(
        turnIndex,
        'No se pudo conectar con el servidor de consultas en este momento.',
      );
    } on FormatException {
      _failTurn(
        turnIndex,
        'La respuesta del asistente no tuvo el formato esperado.',
      );
    } finally {
      if (identical(_activeCancel, cancel)) _activeCancel = null;
      _isBusy = false;
      if (!_disposed) notifyListeners();
    }
  }

  void _applyEvent(int index, ChatSseEvent event) {
    final current = _turns[index];
    switch (event.event) {
      case 'tool':
        final tool = event.data['tool'] as String?;
        final ok = event.data['ok'] as bool? ?? true;
        final step = ChatToolStep(
          stepTitle: chatToolStepTitle(tool),
          summary: chatToolStepSummary(tool, event.data['summary'] as String?),
          isError: !ok,
        );
        _turns[index] = current.copyWith(steps: [...current.steps, step]);
      case 'message':
        final nextSession = event.data['session_id'] as String?;
        if (nextSession != null && nextSession.isNotEmpty) {
          _sessionId = nextSession;
        }
        final tools = (event.data['tools_called'] as List<Object?>? ?? const [])
            .whereType<String>();
        final steps = current.steps.isNotEmpty
            ? current.steps
            : [
                for (final t in tools)
                  ChatToolStep(
                    stepTitle: chatToolStepTitle(t),
                    summary: chatToolStepSummary(t, null),
                  ),
              ];
        _turns[index] = current.copyWith(
          steps: steps,
          assistantMessage: event.data['message'] as String? ?? '',
          isStreaming: false,
        );
      case 'error':
        final detail = event.data['detail'] as String?;
        _turns[index] = current.copyWith(
          errorMessage:
              detail ?? 'El servicio de inferencia interrumpió la respuesta.',
          isStreaming: false,
        );
    }
    notifyListeners();
  }

  void _failTurn(int index, String message) {
    if (_disposed) return;
    _turns[index] = _turns[index].copyWith(
      errorMessage: message,
      isStreaming: false,
    );
  }

  static String _mapApiError(ApiException error) {
    if (error.statusCode == 503) {
      return 'El servidor de lenguaje local aún no está inicializado en este '
          'entorno. Cuando esté activo, el asistente ejecutará las consultas '
          'sobre el modelo y mostrará aquí cada paso.';
    }
    return error.detail ?? 'No se pudo completar la consulta en este momento.';
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
