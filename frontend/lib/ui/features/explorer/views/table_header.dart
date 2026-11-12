/// The sticky header line of the market table: it sits outside the scroll
/// view, so it stays put while the rows scroll.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import 'ledger_layout.dart';

/// Jugador | Edad | Posición | Mercado | Valor estimado | Brecha.
class TableHeader extends StatelessWidget {
  const TableHeader({super.key, required this.dossierOpen});

  final bool dossierOpen;

  @override
  Widget build(BuildContext context) {
    Widget label(String text) => Semantics(
      header: true,
      child: Text(
        text,
        maxLines: 1,
        softWrap: false,
        style: DelphosText.ui(
          size: TypeScale.secondary,
          weight: FontWeight.w500,
          color: DelphosColors.ink3,
        ),
      ),
    );
    return DecoratedBox(
      decoration: const BoxDecoration(
        color: DelphosColors.surfaceSubtle,
        border: Border(bottom: BorderSide(color: DelphosColors.rule)),
      ),
      child: SizedBox(
        height: 37,
        child: LedgerLayout(
          dossierOpen: dossierOpen,
          verticalPadding: 0,
          player: label('Jugador'),
          age: label('Edad'),
          position: label('Posición'),
          market: label('Mercado'),
          estimate: label('Valor estimado'),
          gap: label('Brecha'),
        ),
      ),
    );
  }
}
