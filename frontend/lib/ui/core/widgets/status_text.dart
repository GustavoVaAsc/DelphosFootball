/// The valuation verdict as plain coloured text, with no ground (DESIGN.md
/// §2): `--up` for Infravalorado, `--down` for Sobrevalorado, ink for En
/// precio. The text always names the verdict, so colour is never the only
/// signal.
library;

import 'package:flutter/widgets.dart';

import '../../../domain/models/valuation_status.dart';
import '../labels/valuation_labels.dart';
import '../theme/delphos_colors.dart';
import '../theme/delphos_text.dart';
import '../theme/type_scale.dart';

/// One verdict as a word.
class StatusText extends StatelessWidget {
  const StatusText({super.key, required this.status});

  final ValuationStatus status;

  @override
  Widget build(BuildContext context) {
    return Text(
      valuationStatusLabel(status),
      maxLines: 1,
      softWrap: false,
      style: DelphosText.ui(
        size: TypeScale.secondary,
        weight: FontWeight.w600,
        color: switch (status) {
          ValuationStatus.undervalued => DelphosColors.up,
          ValuationStatus.fair => DelphosColors.ink,
          ValuationStatus.overvalued => DelphosColors.down,
        },
        tabular: true,
      ),
    );
  }
}
