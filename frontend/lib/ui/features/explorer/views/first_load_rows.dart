/// The staggered first load of the market table (DESIGN.md §5): the first 12
/// rows enter 30 ms apart (the last ends before 600 ms), once, when the app
/// first shows the view. Only rows built in the frame that receives the first
/// page play it; rows scrolled in, filtered in or rebuilt later show as is.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/motion.dart';
import '../../../core/widgets/enter_motion.dart';

/// Tracks the first-load rows for one table.
class FirstLoadRows {
  static const int _max = 12;

  Set<int> _ids = const {};
  bool _taken = false;

  /// Call on every build that has rows: the first call with [enabled] claims
  /// the first rows' ids, and the claim ends with that frame.
  void observe({required bool enabled, required List<int> playerIds}) {
    if (!enabled || _taken) return;
    _taken = true;
    _ids = {...playerIds.take(_max)};
    // The list builds its rows in this frame.
    WidgetsBinding.instance.addPostFrameCallback((_) => _ids = const {});
  }

  /// [row] for the player at [index], inside its entry. The wrapper is always
  /// there, so a row keeps its State whether or not it plays.
  Widget wrap({
    required int index,
    required int playerId,
    required Widget row,
  }) {
    return EnterMotion(
      key: ValueKey(playerId),
      offset: const Offset(0, 6),
      delay: DelphosMotion.stagger * index,
      animate: _ids.contains(playerId),
      child: row,
    );
  }
}
