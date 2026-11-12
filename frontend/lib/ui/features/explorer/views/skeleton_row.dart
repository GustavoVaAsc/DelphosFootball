/// A static placeholder row for the table's loading state (DESIGN.md §7:
/// eight static blocks, no shimmer, no pulse).
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import 'ledger_layout.dart';
import 'player_row.dart';

/// One skeleton line laid out on the table's columns.
class SkeletonRow extends StatelessWidget {
  const SkeletonRow({super.key, required this.dossierOpen});

  final bool dossierOpen;

  static Widget _block(double width, double height, {double radius = 4}) =>
      Container(
        width: width,
        height: height,
        decoration: BoxDecoration(
          color: DelphosColors.surfaceMuted,
          borderRadius: BorderRadius.circular(radius),
        ),
      );

  @override
  Widget build(BuildContext context) {
    return ExcludeSemantics(
      child: Container(
        height: PlayerRow.extent,
        decoration: const BoxDecoration(
          border: Border(bottom: BorderSide(color: DelphosColors.rule)),
        ),
        child: LedgerLayout(
          dossierOpen: dossierOpen,
          player: Row(
            spacing: 12,
            children: [
              _block(44, 44, radius: 22),
              // Flexible: the blocks shrink with a narrow Jugador column.
              Flexible(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  spacing: 8,
                  children: [_block(120, 10), _block(90, 10), _block(70, 10)],
                ),
              ),
            ],
          ),
          age: _block(20, 10),
          position: Row(
            spacing: 9,
            children: [_block(36, 24, radius: 3), _block(60, 10)],
          ),
          market: _block(50, 10),
          estimate: _block(50, 10),
          gap: _block(84, 20, radius: 999),
        ),
      ),
    );
  }
}
