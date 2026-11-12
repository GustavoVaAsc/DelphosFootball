/// The explorer actions that only compute a new URL query: filters, pages
/// and the dossier. Split from `ExplorerViewModel` so the loading logic and
/// the actions each fit the module budget.
library;

import 'package:flutter/foundation.dart';

import '../../../../domain/models/player_page.dart';
import '../../../../domain/models/valuation_status.dart';
import '../../../../routing/explorer_query.dart';
import '../../../../routing/explorer_query_edits.dart';

/// Filter, page and dossier actions over [query]; each one calls [navigate].
mixin ExplorerQueryActions {
  ExplorerQuery get query;
  PlayerPage? get page;

  /// Changes the URL to [next]; the router applies it back.
  @protected
  void navigate(ExplorerQuery next);

  void setStatusFilter(ValuationStatus? value) =>
      navigate(query.copyWith(status: value, page: 1));

  void setPosition(String? value) =>
      navigate(query.copyWith(position: value, page: 1));

  void setCluster(int? value) =>
      navigate(query.copyWith(clusterId: value, page: 1));

  /// Moves to [target] when it is a real page; otherwise does nothing.
  void goToPage(int target) {
    final pages = page?.totalPages ?? 0;
    if (target < 1 || target > pages || target == query.page) return;
    navigate(query.copyWith(page: target));
  }

  /// Opens [playerId]'s dossier, or closes it when it is already open.
  void togglePlayer(int playerId) => navigate(
    query.copyWith(playerId: query.playerId == playerId ? null : playerId),
  );

  void closeDossier() => navigate(query.copyWith(playerId: null));
}
