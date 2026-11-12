/// The dossier's season grid (DESIGN.md §4, Season): eight figures in a
/// 4 x 2 grid with the starts and share guards, or one plain sentence when
/// the player has no season row (DESIGN.md §7, no-season). A label that
/// does not fit wraps to a second line rather than truncating; each row is
/// one height and its values sit on a shared line under the labels.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/season_stats.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import 'dossier_text.dart';

/// The season figures, or the no-season sentence for `null`.
class SeasonSection extends StatelessWidget {
  const SeasonSection({super.key, required this.season});

  final SeasonStats? season;

  @override
  Widget build(BuildContext context) {
    final s = season;
    if (s == null) {
      return Text(
        'Sin estadísticas de temporada para este jugador.',
        style: DelphosText.ui(color: DelphosColors.ink2),
      );
    }
    final metrics = seasonMetrics(s);
    Widget cell((String, String) metric) => Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        spacing: 2,
        children: [
          Text(
            metric.$1,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: DelphosText.ui(
              size: TypeScale.label,
              weight: FontWeight.w500,
              color: DelphosColors.ink3,
              height: 1.2,
            ),
          ),
          Text(metric.$2, style: DelphosText.condensed()),
        ],
      ),
    );
    return Column(
      spacing: 12,
      children: [
        for (final row in [metrics.sublist(0, 4), metrics.sublist(4)])
          IntrinsicHeight(
            child: Row(
              spacing: 12,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [for (final m in row) cell(m)],
            ),
          ),
      ],
    );
  }
}
