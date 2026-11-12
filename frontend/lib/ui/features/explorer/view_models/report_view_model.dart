/// The state of the dossier's Resumen (DESIGN.md §4, ADR-018 and ADR-019).
///
/// On a player it looks for a stored report (`GET /reports`) without ever
/// starting a generation. "Generar informe" and "Regenerar" call
/// `POST /reports/generate`, which can take up to two minutes: the elapsed
/// seconds tick once a second, and the request is aborted when the reader
/// cancels, switches player or closes the dossier. A generation counter
/// drops any answer that arrives for a request that is no longer current.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../../../data/repositories/report_repository.dart';
import '../../../../domain/models/scouting_report.dart';
import 'report_status.dart';

/// Loads and generates the report of one player at a time.
class ReportViewModel extends ChangeNotifier {
  ReportViewModel({required this._reports});

  final ReportRepository _reports;

  int? _playerId;
  ReportStatus _status = ReportStatus.idle;
  ScoutingReport? _report;
  int _elapsed = 0;
  bool _generationFailed = false;
  bool _lastForce = false;
  int _generation = 0;
  Timer? _ticker;
  Completer<void>? _cancel;
  bool _disposed = false;

  ReportStatus get status => _status;
  ScoutingReport? get report => _report;

  /// Whole seconds since the current generation started.
  int get elapsedSeconds => _elapsed;

  /// Whether the error is a failed generation (`true`) or lookup.
  bool get generationFailed => _generationFailed;

  /// Shows [playerId]'s report, or nothing for `null`. Anything in flight
  /// for the previous player is aborted.
  void show(int? playerId) {
    if (playerId == _playerId) return;
    _stop();
    _playerId = playerId;
    _report = null;
    _status = playerId == null ? ReportStatus.idle : ReportStatus.checking;
    notifyListeners();
    if (playerId != null) _lookUp(playerId);
  }

  /// Asks for the report; the backend returns a cached one when it has it.
  void generate() => _generate(force: false);

  /// Asks for a new report even when one is cached.
  void regenerate() => _generate(force: true);

  /// Aborts the generation in flight and shows what was there before.
  void cancel() {
    if (_status != ReportStatus.generating) return;
    _stop();
    _status = _report == null ? ReportStatus.none : ReportStatus.ready;
    notifyListeners();
  }

  /// Repeats the request that failed.
  Future<void> retry() async {
    final id = _playerId;
    if (id == null || _status != ReportStatus.error) return;
    if (_generationFailed) return _generate(force: _lastForce);
    _status = ReportStatus.checking;
    notifyListeners();
    return _lookUp(id);
  }

  Future<void> _lookUp(int id) async {
    final generation = _generation;
    var failed = false;
    ScoutingReport? stored;
    try {
      stored = await _reports.latestFor(id);
    } on Exception {
      failed = true;
    }
    if (!_isCurrent(generation)) return;
    _report = stored;
    _generationFailed = false;
    _status = failed
        ? ReportStatus.error
        : (stored == null ? ReportStatus.none : ReportStatus.ready);
    notifyListeners();
  }

  Future<void> _generate({required bool force}) async {
    final id = _playerId;
    if (id == null || _status == ReportStatus.generating) return;
    _stop();
    final generation = _generation;
    final cancel = _cancel = Completer<void>();
    _lastForce = force;
    _status = ReportStatus.generating;
    // The elapsed seconds are the only progress the backend gives.
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) {
      _elapsed++;
      notifyListeners();
    });
    notifyListeners();
    ScoutingReport? fresh;
    try {
      fresh = await _reports.generate(
        id,
        forceRegenerate: force,
        cancel: cancel.future,
      );
    } on Exception {
      fresh = null;
    }
    if (!_isCurrent(generation)) return;
    _ticker?.cancel();
    _report = fresh ?? _report;
    _generationFailed = true;
    _status = fresh == null ? ReportStatus.error : ReportStatus.ready;
    notifyListeners();
  }

  bool _isCurrent(int generation) => !_disposed && generation == _generation;

  /// Makes every request in flight stale and aborts a generation.
  void _stop() {
    _generation++;
    _ticker?.cancel();
    _elapsed = 0;
    final cancel = _cancel;
    _cancel = null;
    if (cancel != null && !cancel.isCompleted) cancel.complete();
  }

  @override
  void dispose() {
    _disposed = true;
    _stop();
    super.dispose();
  }
}
