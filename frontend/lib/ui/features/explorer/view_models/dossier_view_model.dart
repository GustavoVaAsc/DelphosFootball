/// The state of the player dossier (DESIGN.md §4, Dossier).
///
/// The identity (`/players/{id}`), the valuation (`/valuation`) and the
/// replacements (`/replacements`) load in parallel, and each keeps its own
/// state, so one failing call never blanks the others. A 404 on valuation
/// or replacements means the pipeline has nothing for this player: that
/// section is "absent", not an error. The Resumen has its own
/// [ReportViewModel], owned here and moved to the same player, so its
/// once-a-second ticks during a generation rebuild only that section.
library;

import 'package:flutter/foundation.dart';

import '../../../../data/repositories/player_repository.dart';
import '../../../../data/repositories/report_repository.dart';
import '../../../../domain/models/player_profile.dart';
import '../../../../domain/models/player_valuation.dart';
import '../../../../domain/models/replacement_set.dart';
import '../../../core/view_models/load_section.dart';
import '../../../core/view_models/section_load.dart';
import '../../../core/view_models/section_status.dart';
import 'report_view_model.dart';

/// Loads what the dossier shows for one player at a time.
class DossierViewModel extends ChangeNotifier {
  DossierViewModel({required this._players, required ReportRepository reports})
    : report = ReportViewModel(reports: reports);

  final PlayerRepository _players;

  /// The Resumen of the player on show.
  final ReportViewModel report;

  int? _playerId;
  SectionLoad<PlayerProfile> _identity = const SectionLoad.loading();
  SectionLoad<PlayerValuation> _valuation = const SectionLoad.loading();
  SectionLoad<ReplacementSet> _replacements = const SectionLoad.loading();
  int _generation = 0;
  bool _disposed = false;

  /// The player on show, or `null` when the dossier is closed.
  int? get playerId => _playerId;
  SectionLoad<PlayerProfile> get identity => _identity;
  SectionLoad<PlayerValuation> get valuation => _valuation;
  SectionLoad<ReplacementSet> get replacements => _replacements;
  PlayerProfile? get profile => _identity.value;

  /// Shows [playerId]'s dossier, or clears it for `null`. Showing the
  /// player already on show does nothing.
  void show(int? playerId) {
    if (playerId == _playerId) return;
    _playerId = playerId;
    _generation++;
    _identity = const SectionLoad.loading();
    _valuation = const SectionLoad.loading();
    _replacements = const SectionLoad.loading();
    report.show(playerId);
    notifyListeners();
    if (playerId != null) _loadAll(playerId, _generation);
  }

  /// Reloads the sections that failed, and only those.
  Future<void> retry() async {
    final id = _playerId;
    if (id == null) return;
    final generation = _generation;
    bool failed(SectionLoad<Object> load) => load.status == SectionStatus.error;
    await Future.wait([
      if (failed(_identity)) _loadIdentity(id, generation),
      if (failed(_valuation)) _loadValuation(id, generation),
      if (failed(_replacements)) _loadReplacements(id, generation),
    ]);
  }

  Future<void> _loadAll(int id, int generation) => Future.wait([
    _loadIdentity(id, generation),
    _loadValuation(id, generation),
    _loadReplacements(id, generation),
  ]);

  Future<void> _loadIdentity(int id, int generation) => _load(
    generation,
    () => _players.getProfile(id),
    (load) => _identity = load,
    absentOnNotFound: false,
  );

  Future<void> _loadValuation(int id, int generation) => _load(
    generation,
    () => _players.getValuation(id),
    (load) => _valuation = load,
  );

  Future<void> _loadReplacements(int id, int generation) => _load(
    generation,
    () => _players.getReplacements(id),
    (load) => _replacements = load,
  );

  Future<void> _load<T>(
    int generation,
    Future<T> Function() fetch,
    void Function(SectionLoad<T> load) store, {
    bool absentOnNotFound = true,
  }) async {
    if (generation == _generation) {
      store(SectionLoad<T>.loading());
      notifyListeners();
    }
    final result = await loadSection(fetch, absentOnNotFound: absentOnNotFound);
    if (_disposed || generation != _generation) return;
    store(result);
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    report.dispose();
    super.dispose();
  }
}
