/// The comparator's player search (DESIGN.md §4: "Player selector above
/// the table"): the field's text, up to ten suggestions from `/players?name=`
/// 300 ms after the last keystroke, and the keyboard highlight. An answer
/// that a newer search overtook is dropped.
library;

import 'package:flutter/foundation.dart';

import '../../../../data/repositories/player_repository.dart';
import '../../../../domain/models/player_query.dart';
import '../../../../domain/models/player_summary.dart';
import '../../../core/util/debouncer.dart';

/// Suggestions for a typed name.
class PlayerSearchViewModel extends ChangeNotifier {
  PlayerSearchViewModel({
    required this._players,
    Duration debounce = const Duration(milliseconds: 300),
  }) : _debouncer = Debouncer(debounce);

  /// The most suggestions the list shows.
  static const int maxResults = 10;

  final PlayerRepository _players;
  final Debouncer _debouncer;

  String _text = '';
  List<PlayerSummary> _results = const [];
  bool _open = false;
  bool _loading = false;
  bool _failed = false;
  int _highlighted = -1;
  int _generation = 0;
  bool _disposed = false;

  String get text => _text;
  List<PlayerSummary> get results => _results;

  /// Whether the suggestion list is showing.
  bool get isOpen => _open;
  bool get isLoading => _loading;

  /// Whether the last search failed.
  bool get failed => _failed;

  /// The index of the keyboard-highlighted suggestion, or -1.
  int get highlighted => _highlighted;

  PlayerSummary? get highlightedPlayer =>
      _highlighted >= 0 && _highlighted < _results.length
      ? _results[_highlighted]
      : null;

  /// Updates the field now and searches 300 ms after the last keystroke.
  void setText(String text) {
    _text = text;
    final name = text.trim();
    if (name.isEmpty) {
      _debouncer.cancel();
      _generation++;
      _results = const [];
      _open = false;
      _loading = false;
      _failed = false;
      _highlighted = -1;
    } else {
      _debouncer.run(() => _search(name));
    }
    notifyListeners();
  }

  /// Moves the highlight by [delta], staying on the list.
  void moveHighlight(int delta) {
    if (_results.isEmpty) return;
    _highlighted = (_highlighted + delta).clamp(0, _results.length - 1);
    notifyListeners();
  }

  void close() {
    _open = false;
    notifyListeners();
  }

  Future<void> _search(String name) async {
    final generation = ++_generation;
    _loading = true;
    _open = true;
    notifyListeners();
    try {
      final page = await _players.listPlayers(
        PlayerQuery(name: name, pageSize: maxResults),
      );
      if (_disposed || generation != _generation) return;
      _results = page.players;
      _failed = false;
      _highlighted = _results.isEmpty ? -1 : 0;
    } on Exception {
      if (_disposed || generation != _generation) return;
      _results = const [];
      _failed = true;
      _highlighted = -1;
    }
    _loading = false;
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _debouncer.cancel();
    super.dispose();
  }
}
