/// The market table's rows, built lazily at a fixed extent (DESIGN.md §4),
/// each inside its first-load entry.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/player_summary.dart';
import '../view_models/explorer_view_model.dart';
import 'first_load_rows.dart';
import 'player_row.dart';
import 'row_focus_registry.dart';

/// The rows of one page.
class PlayerList extends StatelessWidget {
  const PlayerList({
    super.key,
    required this.players,
    required this.vm,
    required this.rowFocus,
    required this.scroll,
    required this.firstLoad,
    required this.dossierOpen,
    required this.selectedId,
  });

  final List<PlayerSummary> players;
  final ExplorerViewModel vm;
  final RowFocusRegistry rowFocus;
  final ScrollController scroll;
  final FirstLoadRows firstLoad;
  final bool dossierOpen;
  final int? selectedId;

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      controller: scroll,
      itemExtent: PlayerRow.extent,
      itemCount: players.length,
      itemBuilder: (context, index) {
        final player = players[index];
        return firstLoad.wrap(
          index: index,
          playerId: player.id,
          row: PlayerRow(
            player: player,
            selected: dossierOpen && selectedId == player.id,
            dossierOpen: dossierOpen,
            onToggle: () => vm.togglePlayer(player.id),
            nameFocusNode: rowFocus.nodeFor(player.id),
          ),
        );
      },
    );
  }
}
