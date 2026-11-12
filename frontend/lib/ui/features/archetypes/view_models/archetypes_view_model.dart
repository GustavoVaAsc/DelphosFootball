/// The state of the Arquetipos Tácticos view (DESIGN.md §4).
///
/// It loads `/clusters`, then each archetype's four representative players
/// (`/players?cluster_id=<id>&page_size=4`; the API lists by market value,
/// highest first) in parallel. The lists follow the ids the overview
/// returns, so a new archetype needs no code change. One failing list stays
/// inside its own card.
library;

import 'package:flutter/foundation.dart';

import '../../../../data/repositories/archetype_repository.dart';
import '../../../../data/repositories/player_repository.dart';
import '../../../../domain/models/archetype_overview.dart';
import '../../../../domain/models/player_query.dart';
import '../../../../domain/models/player_summary.dart';
import '../../../core/view_models/load_section.dart';
import '../../../core/view_models/section_load.dart';

/// Loads the archetype overview and the representative players.
class ArchetypesViewModel extends ChangeNotifier {
  ArchetypesViewModel({required this._archetypes, required this._players});

  /// Representative players per card.
  static const int representativeCount = 4;

  final ArchetypeRepository _archetypes;
  final PlayerRepository _players;

  SectionLoad<ArchetypeOverview> _overview = const SectionLoad.loading();
  final Map<int, SectionLoad<List<PlayerSummary>>> _representatives = {};
  int _generation = 0;
  bool _disposed = false;

  SectionLoad<ArchetypeOverview> get overview => _overview;

  /// One archetype's representative players; loading until they arrive.
  SectionLoad<List<PlayerSummary>> representatives(int clusterId) =>
      _representatives[clusterId] ?? const SectionLoad.loading();

  /// Loads (or reloads) everything.
  Future<void> load() async {
    final generation = ++_generation;
    bool current() => !_disposed && generation == _generation;
    _overview = const SectionLoad.loading();
    _representatives.clear();
    notifyListeners();
    final overview = await loadSection(
      _archetypes.getOverview,
      absentOnNotFound: false,
    );
    if (!current()) return;
    _overview = overview;
    notifyListeners();
    await Future.wait([
      for (final archetype in overview.value?.archetypes ?? const [])
        loadSection(
          () => _players.listPlayers(
            PlayerQuery(
              clusterId: archetype.clusterId,
              pageSize: representativeCount,
            ),
          ),
          absentOnNotFound: false,
        ).then((load) {
          if (!current()) return;
          _representatives[archetype.clusterId] = switch (load.value) {
            final page? => SectionLoad.ready(page.players),
            null => SectionLoad.error(),
          };
          notifyListeners();
        }),
    ]);
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
