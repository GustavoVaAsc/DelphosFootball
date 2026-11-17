/// The column grid of the market table (DESIGN.md §4, Market table):
/// Jugador | Edad | Posición | Mercado | Valor estimado | Brecha.
///
/// Fixed widths include the cell padding: with the dossier open,
/// 58 / 142 / 88 / 110 / 112 px; with the dossier closed,
/// 80 / 204 / 108 / 126 / 128 px; Jugador takes the rest. Posición rows stay
/// left-aligned so the pitch glyphs line up vertically across every row, while
/// the table header centres the Posición title via [centerPosition]. Edad,
/// Mercado, Valor estimado and Brecha are centred. Posición (142 px open)
/// fits its longest single word ("Mediocentro" beside the 36 px glyph), so a
/// label wraps only between words. See ADR-027. Cells have 8 px a side (16 px
/// between columns) and 14 px at the row edges. The header, the rows and the
/// skeleton rows all lay out through this one widget, so their columns cannot
/// drift apart.
library;

import 'package:flutter/widgets.dart';

/// Lays out the six cells of one table line.
class LedgerLayout extends StatelessWidget {
  const LedgerLayout({
    super.key,
    required this.dossierOpen,
    required this.player,
    required this.age,
    required this.position,
    required this.market,
    required this.estimate,
    required this.gap,
    this.verticalPadding = 10,
    this.centerPosition = false,
  });

  final bool dossierOpen;
  final Widget player;
  final Widget age;
  final Widget position;
  final Widget market;
  final Widget estimate;
  final Widget gap;
  final double verticalPadding;
  final bool centerPosition;

  static const Key positionCellKey = ValueKey('ledger-position-cell');
  static const double positionOpenWidth = 142;
  static const double positionClosedWidth = 204;
  static const double marketWidth = 88;
  static const double _edge = 14;
  static const double _side = 8;

  @override
  Widget build(BuildContext context) {
    Widget cell(
      Widget child, {
      Key? key,
      double? width,
      bool centered = false,
      bool first = false,
      bool last = false,
    }) {
      final padded = Padding(
        padding: EdgeInsets.fromLTRB(
          first ? _edge : _side,
          verticalPadding,
          last ? _edge : _side,
          verticalPadding,
        ),
        child: Align(
          alignment: centered ? Alignment.center : Alignment.centerLeft,
          child: child,
        ),
      );
      return width == null
          ? Expanded(key: key, child: padded)
          : SizedBox(key: key, width: width, child: padded);
    }

    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        cell(player, first: true),
        cell(age, width: dossierOpen ? 58 : 80, centered: true),
        cell(
          position,
          key: positionCellKey,
          width: dossierOpen ? positionOpenWidth : positionClosedWidth,
          centered: centerPosition,
        ),
        cell(market, width: dossierOpen ? marketWidth : 108, centered: true),
        cell(estimate, width: dossierOpen ? 110 : 126, centered: true),
        cell(gap, width: dossierOpen ? 112 : 128, centered: true, last: true),
      ],
    );
  }
}
