/// The valuation verdict pill, the only pill in the app (DESIGN.md §2):
/// green for Infravalorado, ink on muted for En precio, red for
/// Sobrevalorado. The text always names the verdict, so colour is never the
/// only signal.
library;

import 'package:flutter/widgets.dart';

import '../../../domain/models/valuation_status.dart';
import '../labels/valuation_labels.dart';
import '../theme/delphos_colors.dart';
import '../theme/delphos_text.dart';
import '../theme/type_scale.dart';

/// One verdict as a pill.
class StatusPill extends StatelessWidget {
  const StatusPill({super.key, required this.status});

  final ValuationStatus status;

  @override
  Widget build(BuildContext context) {
    final (foreground, background) = switch (status) {
      ValuationStatus.undervalued => (DelphosColors.up, DelphosColors.upBg),
      ValuationStatus.fair => (DelphosColors.ink, DelphosColors.surfaceMuted),
      ValuationStatus.overvalued => (DelphosColors.down, DelphosColors.downBg),
    };
    return DecoratedBox(
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        child: Text(
          valuationStatusLabel(status),
          maxLines: 1,
          softWrap: false,
          style: DelphosText.ui(
            size: TypeScale.secondary,
            weight: FontWeight.w600,
            color: foreground,
            tabular: true,
          ),
        ),
      ),
    );
  }
}
