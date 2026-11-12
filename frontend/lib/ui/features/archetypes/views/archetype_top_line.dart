/// The first row of an archetype card: the short name and the player
/// count (DESIGN.md §4).
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/archetype.dart';
import '../../../core/format/format.dart';
import '../../../core/labels/archetypes.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';

/// Short name on the left, "1.219 jugadores" on the right.
class ArchetypeTopLine extends StatelessWidget {
  const ArchetypeTopLine({super.key, required this.archetype});

  final Archetype archetype;

  @override
  Widget build(BuildContext context) => Row(
    spacing: 8,
    children: [
      Expanded(
        child: Text(
          archetypeShortName(archetype.clusterId) ?? '',
          style: DelphosText.ui(
            weight: FontWeight.w600,
            color: DelphosColors.ink2,
          ),
        ),
      ),
      Text(
        formatCount(archetype.playerCount, 'jugador', 'jugadores'),
        style: DelphosText.ui(weight: FontWeight.w700, tabular: true),
      ),
    ],
  );
}
