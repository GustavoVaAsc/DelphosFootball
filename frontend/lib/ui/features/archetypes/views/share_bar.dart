/// The archetype share bar (DESIGN.md §4 and §2): one stacked bar, a
/// segment per archetype sized by its player count, in ink tones only
/// (ink, ink-2, control border) with 2 px gaps, and a legend aligned under
/// each segment: the name, then "1.219 · 22%".
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/archetype_overview.dart';
import '../../../core/format/numbers.dart';
import '../../../core/labels/archetypes.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import 'share_legend_item.dart';

/// The share of each archetype in the player total.
class ShareBar extends StatelessWidget {
  const ShareBar({super.key, required this.overview});

  final ArchetypeOverview overview;

  static const List<Color> _tones = [
    DelphosColors.ink,
    DelphosColors.ink2,
    DelphosColors.controlBorder,
  ];

  /// The key of the bar segment for [clusterId], for tests.
  static Key segmentKey(int clusterId) => ValueKey(('share-bar', clusterId));

  /// Whole percentages, as the preview rounds them.
  static int shareOf(int count, int total) =>
      total == 0 ? 0 : (count / total * 100).round();

  @override
  Widget build(BuildContext context) {
    final total = overview.totalPlayers;
    final archetypes = overview.archetypes;
    final described = archetypes
        .map(
          (a) =>
              '${archetypeShortName(a.clusterId) ?? ''}: '
              '${formatNumber(a.playerCount)} (${shareOf(a.playerCount, total)}%)',
        )
        .join(', ');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      spacing: 8,
      children: [
        Text(
          'Reparto de los ${formatNumber(total)} jugadores por arquetipo',
          style: DelphosText.ui(
            size: TypeScale.secondary,
            weight: FontWeight.w500,
            color: DelphosColors.ink3,
          ),
        ),
        Semantics(
          label: described,
          image: true,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(3),
            child: SizedBox(
              height: 12,
              // Stretch: a childless ColoredBox takes the smallest size it
              // is allowed, so a loose height would draw nothing.
              child: Row(
                spacing: 2,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  for (var i = 0; i < archetypes.length; i++)
                    Expanded(
                      flex: archetypes[i].playerCount,
                      child: ColoredBox(
                        key: segmentKey(archetypes[i].clusterId),
                        color: _tones[i % _tones.length],
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
        ExcludeSemantics(
          child: Row(
            spacing: 2,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (var i = 0; i < archetypes.length; i++)
                Expanded(
                  flex: archetypes[i].playerCount,
                  child: ShareLegendItem(
                    name: archetypeShortName(archetypes[i].clusterId) ?? '',
                    count:
                        '${formatNumber(archetypes[i].playerCount)} · '
                        '${shareOf(archetypes[i].playerCount, total)}%',
                    tone: _tones[i % _tones.length],
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}
