/// The column grid of the market table (DESIGN.md §4, Market table):
/// Jugador | Edad | Posición | Mercado | Valor estimado | Brecha.
///
/// Fixed widths include the cell padding, as in the preview's fixed table
/// layout: 48 / 142 / 76 / 100 / 128 px with the dossier open, Posición
/// 180 px with it closed, and Jugador takes the rest. Two columns are wider
/// than DESIGN.md's 130 and 120 px, measured with Archivo: Posición fits
/// its longest single word ("Mediocentro", 74 px, beside the 36 px glyph),
/// so a label wraps only between words; Brecha fits the widest pill
/// ("Sobrevalorado", 98 px with its padding). See ADR-027. Cells have 8 px a
/// side (16 px between columns) and 14 px at the row edges. The header,
/// the rows and the skeleton rows all lay out through this one widget, so
/// their columns cannot drift apart.
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
  });

  final bool dossierOpen;
  final Widget player;
  final Widget age;
  final Widget position;
  final Widget market;
  final Widget estimate;
  final Widget gap;
  final double verticalPadding;

  static const double _edge = 14;
  static const double _side = 8;

  @override
  Widget build(BuildContext context) {
    Widget cell(
      Widget child, {
      double? width,
      bool end = false,
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
          alignment: end ? Alignment.centerRight : Alignment.centerLeft,
          child: child,
        ),
      );
      return width == null
          ? Expanded(child: padded)
          : SizedBox(width: width, child: padded);
    }

    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        cell(player, first: true),
        cell(age, width: 48, end: true),
        cell(position, width: dossierOpen ? 142 : 180),
        cell(market, width: 76, end: true),
        cell(estimate, width: 100, end: true),
        cell(gap, width: 128, end: true, last: true),
      ],
    );
  }
}
