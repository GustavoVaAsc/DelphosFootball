/// The archetypes view's intro card (DESIGN.md §4): the season, one
/// sentence on what the classification is, with the player total from the
/// data, and the share bar.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/archetype_overview.dart';
import '../../../core/format/format.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import 'share_bar.dart';

/// "Temporada 2025/26", the sentence, and the share bar.
class ArchetypeIntro extends StatelessWidget {
  const ArchetypeIntro({super.key, required this.overview});

  final ArchetypeOverview overview;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      decoration: BoxDecoration(
        color: DelphosColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: DelphosColors.rule),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        spacing: 16,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            spacing: 4,
            children: [
              Semantics(
                header: true,
                child: Text(
                  'Temporada ${formatSeason(overview.season)}',
                  style: DelphosText.ui(
                    size: TypeScale.section,
                    weight: FontWeight.w700,
                  ),
                ),
              ),
              Text(
                'Clasificación de los ${formatNumber(overview.totalPlayers)} '
                'jugadores de campo europeos en tres perfiles según su '
                'producción estadística por 90 minutos.',
                style: DelphosText.ui(color: DelphosColors.ink2),
              ),
            ],
          ),
          ShareBar(overview: overview),
        ],
      ),
    );
  }
}
