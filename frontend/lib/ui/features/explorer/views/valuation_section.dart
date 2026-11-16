/// The dossier's valuation (DESIGN.md §4, Valuation): "Precio de mercado"
/// and "Valor estimado" at 28/700 condensed, one line with the verdict word,
/// " · " and the difference, and the classifier check in neutral ink. The
/// estimate takes the verdict's colour; the classifier lines never do.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/player_valuation.dart';
import '../../../../domain/models/valuation_status.dart';
import '../../../core/format/money.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/count_up_text.dart';
import '../../../core/widgets/status_text.dart';
import 'dossier_text.dart';

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
        // Counts up each time a player loads, through the es-ES money
        // formatter on every frame (DESIGN.md §5).
        CountUpText(
          value: value,
          format: formatEur,
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
        // The status word, " · ", then the difference. If it ever wraps it
        // does so between the two, and the "·" stays with the word.
        Wrap(
          spacing: 6,
          runSpacing: 4,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Row(
              mainAxisSize: MainAxisSize.min,
              spacing: 6,
              children: [
                StatusText(status: v.status),
                ExcludeSemantics(child: Text('·', style: line)),
              ],
            ),
            Text(valuationDifference(v), style: line),
          ],
        ),
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
