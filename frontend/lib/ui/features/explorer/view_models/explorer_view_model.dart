/// The state and actions of the Explorador de Mercado (DESIGN.md §4).
///
/// The URL is the source of truth: the screen passes every parsed
/// [ExplorerQuery] to [applyQuery], and every user action computes a new
/// query and hands it to `navigate`, which changes the URL; the router then
/// calls [applyQuery] again. The ViewModel never changes its own query.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../../../data/repositories/player_repository.dart';
import '../../../../domain/models/player_page.dart';
import '../../../../routing/explorer_query.dart';
import '../../../../routing/explorer_query_edits.dart';
import '../../../core/util/debouncer.dart';
import 'explorer_query_actions.dart';
import 'explorer_status.dart';

/// Loads the market table for the URL's query and turns actions into URLs.
class ExplorerViewModel extends ChangeNotifier with ExplorerQueryActions {
  ExplorerViewModel({
    required this._players,
    required this._navigate,
    Duration searchDebounce = const Duration(milliseconds: 300),
  }) : _search = Debouncer(searchDebounce);

  final PlayerRepository _players;
  final void Function(ExplorerQuery query) _navigate;
  final Debouncer _search;

  ExplorerQuery? _query;
  ExplorerStatus _status = ExplorerStatus.loading;
  PlayerPage? _page;
  bool _refreshing = false;
  String _searchText = '';
  int _generation = 0;
  bool _disposed = false;

  @override
  ExplorerQuery get query => _query ?? const ExplorerQuery();
  ExplorerStatus get status => _status;

  /// The rows on screen; kept while the next page or filter loads.
  @override
  PlayerPage? get page => _page;

  /// Whether a request is running while the previous rows stay shown.
  bool get isRefreshing => _refreshing;

  /// The search field's live text, ahead of the debounced URL.
  String get searchText => _searchText;

  /// Takes the query parsed from the URL and reloads if the rows change.
  void applyQuery(ExplorerQuery next) {
    final previous = _query;
    _query = next;
    if (!_search.isPending) _searchText = next.search ?? '';
    if (previous == null || !previous.sameListAs(next)) {
      unawaited(_load(dropsMissingPlayer: previous != null));
    } else {
      notifyListeners();
    }
  }

  /// Updates the field now and the URL 300 ms after the last keystroke.
  void setSearchText(String text) {
    _searchText = text;
    _search.run(() {
      final trimmed = text.trim();
      navigate(
        query.copyWith(search: trimmed.isEmpty ? null : trimmed, page: 1),
      );
    });
    notifyListeners();
  }

  void resetFilters() {
    _search.cancel();
    _searchText = '';
    navigate(ExplorerQuery(playerId: query.playerId));
  }

  @override
  @protected
  void navigate(ExplorerQuery next) => _navigate(next);

  Future<void> retry() => _load(dropsMissingPlayer: false);

  Future<void> _load({required bool dropsMissingPlayer}) async {
    final generation = ++_generation;
    final request = query;
    _refreshing = _page != null && _status != ExplorerStatus.error;
    if (!_refreshing) _status = ExplorerStatus.loading;
    notifyListeners();
    try {
      final page = await _players.listPlayers(request.toPlayerQuery());
      if (_disposed || generation != _generation) return;
      _page = page;
      _status = page.total == 0 ? ExplorerStatus.empty : ExplorerStatus.ready;
      _refreshing = false;
      notifyListeners();
      _correctAfterLoad(page, dropsMissingPlayer);
    } on Exception {
      if (_disposed || generation != _generation) return;
      _status = ExplorerStatus.error;
      _refreshing = false;
      notifyListeners();
    }
  }

  /// A page past the end moves to the last page. A filter or page change
  /// that drops the open player closes the dossier; a deep link to a player
  /// who is not on the first page keeps it open.
  void _correctAfterLoad(PlayerPage page, bool dropsMissingPlayer) {
    if (page.players.isEmpty && page.totalPages > 0) {
      navigate(query.copyWith(page: page.totalPages));
      return;
    }
    final open = query.playerId;
    if (dropsMissingPlayer &&
        open != null &&
        !page.players.any((player) => player.id == open)) {
      closeDossier();
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _search.cancel();
    super.dispose();
  }
}
