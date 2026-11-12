/// One row of the market table (DESIGN.md §4). The name is the real
/// control; a click anywhere else on the row is a mouse shortcut to it.
/// The selected look (ink tint plus a 3 px ink bar) shows only while this
/// player's dossier is open.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/player_summary.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/motion.dart';
import 'ledger_cells.dart';
import 'ledger_layout.dart';
import 'player_identity_cell.dart';

/// A table row with hover and selected states.
class PlayerRow extends StatefulWidget {
  const PlayerRow({
    super.key,
    required this.player,
    required this.selected,
    required this.dossierOpen,
    required this.onToggle,
    required this.nameFocusNode,
  });

  /// Row height including the 1 px hairline, used as the list's fixed
  /// item extent: 10 px padding above and below the three-line identity
  /// block (name 15/1.25, club and archetype 12/1.3, 3 px of gaps).
  static const double extent = 74;

  final PlayerSummary player;
  final bool selected;
  final bool dossierOpen;
  final VoidCallback onToggle;
  final FocusNode nameFocusNode;

  @override
  State<PlayerRow> createState() => _PlayerRowState();
}

class _PlayerRowState extends State<PlayerRow> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final p = widget.player;
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onTap: widget.onToggle,
        excludeFromSemantics: true,
        // Hover feedback (DESIGN.md §5); the row itself never moves.
        child: AnimatedContainer(
          duration: DelphosMotion.duration(context, DelphosMotion.hover),
          curve: DelphosMotion.easeOut,
          height: PlayerRow.extent,
          decoration: BoxDecoration(
            color: widget.selected
                ? DelphosColors.selectedBg
                : (_hovered
                      ? DelphosColors.surfaceSubtle
                      : DelphosColors.surface),
            border: const Border(bottom: BorderSide(color: DelphosColors.rule)),
          ),
          foregroundDecoration: widget.selected
              ? const BoxDecoration(
                  border: Border(
                    left: BorderSide(color: DelphosColors.ink, width: 3),
                  ),
                )
              : null,
          child: LedgerLayout(
            dossierOpen: widget.dossierOpen,
            player: PlayerIdentityCell(
              player: p,
              dossierOpen: widget.selected,
              onToggle: widget.onToggle,
              nameFocusNode: widget.nameFocusNode,
            ),
            age: LedgerCells.age(p.age),
            position: LedgerCells.position(p),
            market: LedgerCells.market(p.marketValueEur),
            estimate: LedgerCells.estimate(p.fairValueEur, p.valuationStatus),
            gap: LedgerCells.gap(p),
          ),
        ),
      ),
    );
  }
}
