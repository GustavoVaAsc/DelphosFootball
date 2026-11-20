/// State and SSE orchestration for the conversational scouting assistant.
/// The view model is provided by the app, not by the screen, so the
/// conversation on show survives leaving the chat and coming back during the
/// same app run. Clearing and session switching live in `ChatConversation`.
library;

import '../../../../domain/models/chat_turn.dart';
import 'chat_conversation.dart';
import 'chat_turn_errors.dart';
import 'chat_turn_stream.dart';

/// Drives `/chat`: capabilities pop-up visibility and SSE turn streaming.
class ChatViewModel extends ChatConversation {
  ChatViewModel({required super.repository});

  /// Whether the last turn failed and can be sent again.
  bool get canRetry =>
      !isBusy &&
      !isRestoring &&
      turnList.isNotEmpty &&
      turnList.last.errorMessage != null;

  /// Drops the failed last turn and sends its question again.
  Future<void> retryLastTurn() {
    if (!canRetry) return Future.value();
    final text = turnList.removeLast().userMessage;
    return sendMessage(text);
  }

  Future<void> sendMessage(String rawText) async {
    final text = rawText.trim();
    if (text.isEmpty || isBusy || isRestoring) return;
    closeCapabilities();
    final cancel = beginTurn();
    final index = turnList.length;
    turnList.add(ChatTurn(userMessage: text, isStreaming: true));
    notifyListeners();

    try {
      await for (final next in streamChatTurn(
        repository,
        turnList[index],
        sessionId: sessionId,
        cancel: cancel.future,
        onSession: (id) {
          if (!cancel.isCompleted) sessionId = id;
        },
      )) {
        if (isDisposed || cancel.isCompleted) return;
        turnList[index] = next;
        notifyListeners();
      }
    } on Exception catch (error) {
      // After a cancel the turn is gone or replaced: whatever the aborted
      // request threw, there is nothing left to mark as failed.
      if (!isDisposed && !cancel.isCompleted && index < turnList.length) {
        turnList[index] = turnList[index].failed(chatErrorMessage(error));
      }
    } finally {
      endTurn(cancel);
    }
  }
}
