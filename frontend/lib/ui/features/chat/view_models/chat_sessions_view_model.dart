/// State of the chat's "Conversaciones" menu: whether it is open, the saved
/// sessions it lists, and the loading of a picked session's messages. The
/// list is read each time the menu opens; the one on show stays visible while
/// the new one loads, so reopening never flashes a loading state. Applying
/// the loaded messages to the conversation belongs to `ChatViewModel`.
library;

import 'package:flutter/foundation.dart';

import '../../../../data/repositories/chat_repository.dart';
import '../../../../domain/models/chat_session_history.dart';
import '../../../../domain/models/chat_session_summary.dart';
import '../../../core/view_models/load_section.dart';
import '../../../core/view_models/section_load.dart';
import '../../../core/view_models/section_status.dart';

/// Loads the saved conversations for the menu.
class ChatSessionsViewModel extends ChangeNotifier {
  ChatSessionsViewModel({required this._repository});

  final ChatRepository _repository;

  bool _isOpen = false;
  SectionLoad<List<ChatSessionSummary>> _sessions = const SectionLoad.loading();
  int _generation = 0;
  bool _disposed = false;
  String? _restoringId;
  SectionStatus? _restore;
  int _restoreGeneration = 0;

  bool get isOpen => _isOpen;

  /// Whether a picked session's messages are being loaded.
  bool get isRestoring => _restore == SectionStatus.loading;

  /// Whether the last picked session could not be loaded.
  bool get restoreFailed => _restore == SectionStatus.error;

  /// Loading until the first answer; ready (possibly empty) or error after.
  SectionLoad<List<ChatSessionSummary>> get sessions => _sessions;

  void open() {
    if (_isOpen) return;
    _isOpen = true;
    notifyListeners();
    _refresh();
  }

  void close() {
    if (!_isOpen) return;
    _isOpen = false;
    notifyListeners();
  }

  /// Reads the list again after a failure.
  Future<void> retry() {
    if (_sessions.status != SectionStatus.error) return Future.value();
    _sessions = const SectionLoad.loading();
    notifyListeners();
    return _refresh();
  }

  /// Loads the messages of session [id], closing the menu. Completes with
  /// them, or with `null` on a failure ([restoreFailed]) or when a newer
  /// pick or [reset] superseded this one.
  Future<ChatSessionHistory?> restore(String id) async {
    close();
    final generation = ++_restoreGeneration;
    _restoringId = id;
    _restore = SectionStatus.loading;
    notifyListeners();
    final load = await loadSection(
      () => _repository.getSession(id),
      absentOnNotFound: false,
    );
    if (_disposed || generation != _restoreGeneration) return null;
    _restore = load.status == SectionStatus.ready ? null : SectionStatus.error;
    notifyListeners();
    return load.value;
  }

  /// Loads the session that failed to open again.
  Future<ChatSessionHistory?> retryRestore() {
    final id = _restoringId;
    if (!restoreFailed || id == null) return Future.value();
    return restore(id);
  }

  /// Forgets any restore in flight or failed, and closes the menu.
  void reset() {
    _restoreGeneration++;
    _restore = null;
    close();
  }

  Future<void> _refresh() async {
    final generation = ++_generation;
    final next = await loadSection(
      _repository.listSessions,
      absentOnNotFound: false,
    );
    if (_disposed || generation != _generation) return;
    // A failed refresh keeps the list already on show.
    if (next.status == SectionStatus.error &&
        _sessions.status == SectionStatus.ready) {
      return;
    }
    _sessions = next;
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
