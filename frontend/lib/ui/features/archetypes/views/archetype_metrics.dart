/// The averages of an archetype card in a 2 x 2 grid, each named in one
/// word (DESIGN.md §4): Valor, Minutos, Goles and Asistencias promedio.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/archetype.dart';
import '../../../core/format/format.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';

/// The four averages in a 2 x 2 grid.
class ArchetypeMetrics extends StatelessWidget {
  const ArchetypeMetrics({super.key, required this.archetype});

  final Archetype archetype;

  @override
  Widget build(BuildContext context) {
    final a = archetype;
    Widget metric(String label, String value) => Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        spacing: 2,
        children: [
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: DelphosText.ui(
              size: TypeScale.label,
              weight: FontWeight.w500,
              color: DelphosColors.ink3,
              height: 1.2,
            ),
          ),
          Text(value, style: DelphosText.condensed()),
        ],
      ),
    );
    return Column(
      spacing: 12,
      children: [
        Row(
          spacing: 12,
          children: [
            metric('Valor promedio', formatEur(a.avgMarketValueEur)),
            metric('Minutos promedio', formatMinutes(a.avgMinutes)),
          ],
        ),
        Row(
          spacing: 12,
          children: [
            metric('Goles promedio', formatNumber(a.avgGoals, decimals: 1)),
            metric(
              'Asistencias promedio',
              formatNumber(a.avgAssists, decimals: 1),
            ),
          ],
        ),
      ],
    );
  }
}
