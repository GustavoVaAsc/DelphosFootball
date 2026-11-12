/// The dossier's replacement candidates (DESIGN.md §4 and §7): with fewer
/// than three, a plain note above the rows ("N de 3 reemplazos." in ink,
/// then the reason from `shortfall_reason`), never padded with filler; the
/// rows are separated by hairlines.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/replacement_set.dart';
import '../../../core/labels/shortfall.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import 'dossier_text.dart';
import 'replacement_row.dart';

/// The shortfall note and the candidate rows of one replacement set.
class ReplacementsList extends StatelessWidget {
  const ReplacementsList({super.key, required this.set});

  final ReplacementSet set;

  @override
  Widget build(BuildContext context) {
    final shortfall = describeShortfall(
      qualifyingCount: set.qualifyingCount,
      reason: set.shortfallReason,
    );
    final candidates = set.candidates;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      spacing: 10,
      children: [
        if (shortfall != null)
          Text.rich(
            TextSpan(
              style: DelphosText.ui(
                size: TypeScale.secondary,
                color: DelphosColors.ink2,
              ),
              children: [
                TextSpan(
                  text: replacementCountNote(candidates.length),
                  style: DelphosText.ui(
                    size: TypeScale.secondary,
                    weight: FontWeight.w600,
                  ),
                ),
                TextSpan(text: ' $shortfall'),
              ],
            ),
          ),
        for (var i = 0; i < candidates.length; i++)
          Container(
            padding: EdgeInsets.only(top: i == 0 ? 0 : 10),
            decoration: BoxDecoration(
              border: i == 0
                  ? null
                  : const Border(top: BorderSide(color: DelphosColors.rule)),
            ),
            child: ReplacementRow(candidate: candidates[i]),
          ),
      ],
    );
  }
}
