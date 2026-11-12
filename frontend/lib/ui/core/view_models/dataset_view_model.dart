/// Dataset-wide facts the shell shows on every page: the player total, the
/// season and the latest data date, all from `GET /clusters` (DESIGN.md §4:
/// derived from the data, never hard-coded).
library;

import 'package:flutter/foundation.dart';

import '../../../data/repositories/archetype_repository.dart';
import '../../../domain/models/archetype_overview.dart';

/// Loads the archetype overview once for the whole app.
class DatasetViewModel extends ChangeNotifier {
  DatasetViewModel({required this._archetypes});

  final ArchetypeRepository _archetypes;
  ArchetypeOverview? _overview;
  bool _failed = false;
  bool _disposed = false;

  /// The overview, or `null` until it loads (or when it failed).
  ArchetypeOverview? get overview => _overview;

  /// Whether the last load failed; the shell then shows no data line.
  bool get failed => _failed;

  /// Players across all archetypes ("5.522 jugadores").
  int? get totalPlayers => _overview?.totalPlayers;

  /// Fetches the overview; a failure leaves the facts empty.
  Future<void> load() async {
    try {
      final overview = await _archetypes.getOverview();
      if (_disposed) return;
      _overview = overview;
      _failed = false;
    } on Exception {
      if (_disposed) return;
      _failed = true;
    }
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
