/// The state of the Comparador Moneyball (DESIGN.md §4).
///
/// The reference player's profile, valuation and replacements load in
/// parallel; once the replacements arrive, every candidate's profile loads
/// in parallel too (for its league, age and season figures). A candidate
/// whose profile fails is a gap in its own column, never a blank table. A
/// replacements 404 is "absent": the table shows the placeholder column.
library;

import 'package:flutter/foundation.dart';

import '../../../../data/repositories/player_repository.dart';
import '../../../../domain/models/player_profile.dart';
import '../../../../domain/models/player_valuation.dart';
import '../../../../domain/models/replacement_set.dart';
import '../../../core/view_models/load_section.dart';
import '../../../core/view_models/section_load.dart';
import '../../../core/view_models/section_status.dart';
import 'comparator_status.dart';

/// Loads one reference player and its replacement candidates.
class ComparatorViewModel extends ChangeNotifier {
  ComparatorViewModel({required this._players});

  final PlayerRepository _players;

  int? _playerId;
  SectionLoad<PlayerProfile> _reference = const SectionLoad.loading();
  SectionLoad<PlayerValuation> _valuation = const SectionLoad.loading();
  SectionLoad<ReplacementSet> _replacements = const SectionLoad.loading();
  final Map<int, SectionLoad<PlayerProfile>> _candidates = {};
  int _generation = 0;
  bool _disposed = false;

  int? get playerId => _playerId;
  SectionLoad<PlayerProfile> get reference => _reference;
  SectionLoad<PlayerValuation> get valuation => _valuation;
  SectionLoad<ReplacementSet> get replacements => _replacements;

  /// A candidate's profile load; loading until it is asked for.
  SectionLoad<PlayerProfile> candidate(int candidateId) =>
      _candidates[candidateId] ?? const SectionLoad.loading();

  /// The page state: the table needs the reference's profile, valuation and
  /// replacements (or their absence); candidates fill in on their own.
  ComparatorStatus get status {
    if (_playerId == null) return ComparatorStatus.idle;
    final parts = [_reference.status, _valuation.status, _replacements.status];
    if (parts.contains(SectionStatus.error) ||
        _reference.status == SectionStatus.absent) {
      return ComparatorStatus.error;
    }
    if (parts.contains(SectionStatus.loading)) return ComparatorStatus.loading;
    return ComparatorStatus.ready;
  }

  /// Compares [playerId] with its replacements; `null` clears the page.
  void show(int? playerId) {
    if (playerId == _playerId) return;
    _playerId = playerId;
    _load();
  }

  /// Loads everything for the current player again.
  Future<void> retry() => _load();

  Future<void> _load() async {
    final id = _playerId;
    final generation = ++_generation;
    _reference = const SectionLoad.loading();
    _valuation = const SectionLoad.loading();
    _replacements = const SectionLoad.loading();
    _candidates.clear();
    notifyListeners();
    if (id == null) return;
    bool current() => !_disposed && generation == _generation;
    await Future.wait([
      loadSection(
        () => _players.getProfile(id),
        absentOnNotFound: false,
      ).then((load) => _apply(current, () => _reference = load)),
      loadSection(
        () => _players.getValuation(id),
        absentOnNotFound: false,
      ).then((load) => _apply(current, () => _valuation = load)),
      loadSection(() => _players.getReplacements(id)).then((load) async {
        _apply(current, () => _replacements = load);
        final candidates = load.value?.candidates ?? const [];
        await Future.wait([
          for (final c in candidates)
            loadSection(
              () => _players.getProfile(c.playerId),
              absentOnNotFound: false,
            ).then((p) => _apply(current, () => _candidates[c.playerId] = p)),
        ]);
      }),
    ]);
  }

  void _apply(bool Function() current, void Function() change) {
    if (!current()) return;
    change();
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
