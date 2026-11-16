/// The explorer's focus nodes and the rule for where focus goes when the
/// dossier closes (DESIGN.md §4).
library;

import 'package:flutter/widgets.dart';

import 'row_focus_registry.dart';

/// Owns the row, table, search and dossier focus nodes of view 1.
class ExplorerFocus {
  final RowFocusRegistry rows = RowFocusRegistry();
  final FocusNode table = FocusNode(debugLabel: 'player table');
  final FocusNode search = FocusNode(debugLabel: 'player search');
  final FocusNode dossier = FocusNode(
    debugLabel: 'dossier',
    canRequestFocus: false,
    skipTraversal: true,
  );

  /// Focus goes back to the player's name if it was inside the dossier, on
  /// that name already, or nowhere in particular (no node, a scope, or the
  /// table area); anywhere else it stays. [mounted] guards the post-frame
  /// request.
  void returnAfterClose(int playerId, {required bool Function() mounted}) {
    final primary = FocusManager.instance.primaryFocus;
    final moveFocus =
        dossier.hasFocus ||
        primary == null ||
        primary is FocusScopeNode ||
        primary == table ||
        primary == rows.existing(playerId);
    if (!moveFocus) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted()) return;
      (rows.existing(playerId) ?? table).requestFocus();
    });
  }

  void dispose() {
    rows.dispose();
    table.dispose();
    search.dispose();
    dossier.dispose();
  }
}
