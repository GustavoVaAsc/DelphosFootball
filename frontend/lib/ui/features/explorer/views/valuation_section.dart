/// The dossier's valuation (DESIGN.md §4, Valuation): "Precio de mercado"
/// and "Valor estimado" at 28/700 condensed, the verdict pill with the
/// difference, the dumbbell, and the classifier check in neutral ink. The
/// estimate takes the verdict's colour; the classifier lines never do.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/player_valuation.dart';
import '../../../../domain/models/valuation_status.dart';
import '../../../core/format/money.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/status_pill.dart';
import 'dossier_text.dart';
import 'valuation_dumbbell.dart';

/// The valuation block for one player.
class ValuationSection extends StatelessWidget {
  const ValuationSection({super.key, required this.valuation});

  final PlayerValuation valuation;

  @override
  Widget build(BuildContext context) {
    final v = valuation;
    final line = DelphosText.ui(
      size: TypeScale.secondary,
      color: DelphosColors.ink2,
      tabular: true,
    );
    final strong = line.copyWith(
      color: DelphosColors.ink,
      fontWeight: FontWeight.w600,
    );
    Widget figure(String label, double value, Color colour) => Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: 2,
      children: [
        Text(
          label,
          style: DelphosText.ui(
            size: TypeScale.secondary,
            weight: FontWeight.w500,
            color: DelphosColors.ink3,
          ),
        ),
        Text(
          formatEur(value),
          style: DelphosText.condensed(
            size: TypeScale.figure,
            color: colour,
            height: 1.1,
          ),
        ),
      ],
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: 12,
      children: [
        Wrap(
          spacing: 28,
          runSpacing: 8,
          children: [
            figure('Precio de mercado', v.marketValueEur, DelphosColors.ink),
            figure('Valor estimado', v.fairValueEur, switch (v.status) {
              ValuationStatus.undervalued => DelphosColors.up,
              ValuationStatus.overvalued => DelphosColors.down,
              ValuationStatus.fair => DelphosColors.ink,
            }),
          ],
        ),
        Wrap(
          spacing: 8,
          runSpacing: 4,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            StatusPill(status: v.status),
            Text(valuationDifference(v), style: line),
          ],
        ),
        ValuationDumbbell(valuation: v),
        Semantics(
          container: true,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            spacing: 2,
            children: [
              Text('Comprobación de los clasificadores', style: strong),
              Text.rich(
                TextSpan(
                  style: line,
                  children: [
                    const TextSpan(text: 'Random Forest: '),
                    TextSpan(
                      text: rfProbabilityText(v.rfUndervaluedProb),
                      style: strong,
                    ),
                    const TextSpan(text: ' de probabilidad de infravaloración'),
                  ],
                ),
              ),
              Text(
                classifierCheckLine(
                  rf: v.rfUndervaluedPred,
                  dt: v.dtUndervaluedPred,
                  status: v.status,
                ),
                style: line,
              ),
            ],
          ),
        ),
      ],
    );
  }
}
