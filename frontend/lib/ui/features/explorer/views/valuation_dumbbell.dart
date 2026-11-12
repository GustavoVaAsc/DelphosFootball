/// The valuation dumbbell (DESIGN.md §4, Valuation): an axis from €0, the
/// market dot, the estimate dot, the gap between them coloured by the
/// verdict (ink-3 for En precio), and each figure labelled at its dot. No
/// legend. A label near either end aligns to that end instead of centring,
/// so it never leaves the panel. Geometry as in the preview: the axis runs
/// to 108% of the larger figure.
library;

import 'package:flutter/widgets.dart';

import 'dumbbell_painter.dart';

import '../../../../domain/models/player_valuation.dart';
import '../../../../domain/models/valuation_status.dart';
import '../../../core/format/money.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';

/// The price and the estimate on one scale.
class ValuationDumbbell extends StatelessWidget {
  const ValuationDumbbell({super.key, required this.valuation});

  final PlayerValuation valuation;

  @override
  Widget build(BuildContext context) {
    final v = valuation;
    final max =
        (v.marketValueEur > v.fairValueEur
            ? v.marketValueEur
            : v.fairValueEur) *
        1.08;
    double share(double value) => max <= 0 ? 0 : (value / max).clamp(0.0, 1.0);
    final market = share(v.marketValueEur);
    final estimate = share(v.fairValueEur);
    final small = DelphosText.ui(
      size: TypeScale.label,
      color: DelphosColors.ink2,
      tabular: true,
    );
    Widget label(String term, double value, double at, double width) {
      final text = Text.rich(
        TextSpan(
          children: [
            TextSpan(text: '$term ', style: small),
            TextSpan(
              text: formatEur(value),
              style: DelphosText.condensed(size: TypeScale.label),
            ),
          ],
        ),
        maxLines: 1,
        softWrap: false,
      );
      final x = at * width;
      return switch (at) {
        < 0.12 => Positioned(left: x - 6, top: 0, child: text),
        > 0.88 => Positioned(right: width - x - 6, top: 0, child: text),
        _ => Positioned(
          left: x,
          top: 0,
          child: FractionalTranslation(
            translation: const Offset(-0.5, 0),
            child: text,
          ),
        ),
      };
    }

    return Semantics(
      label:
          'Escala desde €0: precio de mercado ${formatEur(v.marketValueEur)}, '
          'valor estimado ${formatEur(v.fairValueEur)}',
      excludeSemantics: true,
      child: Row(
        spacing: 10,
        children: [
          Text('€0', style: small.copyWith(color: DelphosColors.ink3)),
          Expanded(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final width = constraints.maxWidth;
                return Column(
                  children: [
                    SizedBox(
                      height: 16,
                      child: Stack(
                        clipBehavior: Clip.none,
                        children: [
                          label(
                            'Valor estimado',
                            v.fairValueEur,
                            estimate,
                            width,
                          ),
                        ],
                      ),
                    ),
                    CustomPaint(
                      size: Size(width, 14),
                      painter: DumbbellPainter(
                        market: market,
                        estimate: estimate,
                        gapColour: switch (v.status) {
                          ValuationStatus.undervalued => DelphosColors.up,
                          ValuationStatus.overvalued => DelphosColors.down,
                          ValuationStatus.fair => DelphosColors.ink3,
                        },
                      ),
                    ),
                    SizedBox(
                      height: 16,
                      child: Stack(
                        clipBehavior: Clip.none,
                        children: [
                          label('Mercado', v.marketValueEur, market, width),
                        ],
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
