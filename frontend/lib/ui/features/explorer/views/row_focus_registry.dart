/// Focus nodes for the row name buttons, by player id, so the explorer can
/// put focus back on a player's name when the dossier closes (DESIGN.md
/// §4). Rows are built lazily, so a node is created the first time a row
/// asks for it and dropped when its player leaves the page.
library;

import 'package:flutter/widgets.dart';

/// One focus node per visible player.
class RowFocusRegistry {
  final Map<int, FocusNode> _nodes = {};

  /// The node for [playerId]'s name button.
  FocusNode nodeFor(int playerId) => _nodes.putIfAbsent(
    playerId,
    () => FocusNode(debugLabel: 'row name $playerId'),
  );

  /// The node for [playerId] if its row has been built.
  FocusNode? existing(int playerId) => _nodes[playerId];

  /// Drops the nodes of players no longer on the page.
  void retainOnly(Set<int> playerIds) {
    final gone = _nodes.keys.where((id) => !playerIds.contains(id)).toList();
    for (final id in gone) {
      _nodes.remove(id)!.dispose();
    }
  }

  void dispose() {
    for (final node in _nodes.values) {
      node.dispose();
    }
    _nodes.clear();
  }
}
