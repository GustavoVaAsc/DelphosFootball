/// The three archetype cards with their internal rows aligned across cards
/// (DESIGN.md §4, Arquetipos Tácticos), the Flutter stand-in for the
/// preview's CSS subgrid.
///
/// The cards are drawn as a background layer (three bordered boxes), and
/// the content is laid out row by row on top: each row (top line, title
/// block, pitch, metrics, representative players, link) is an
/// IntrinsicHeight row of three cells, so a long title in one card moves
/// the pitches of all three together, and the cards share one height.
library;

import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

import '../../../../domain/models/archetype.dart';
import '../../../../domain/models/player_summary.dart';
import '../../../../routing/explorer_query.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/view_models/section_load.dart';
import '../../../core/widgets/text_link.dart';
import 'archetype_heading.dart';
import 'archetype_metrics.dart';
import 'archetype_pitch.dart';
import 'archetype_top_line.dart';
import 'representative_list.dart';

/// The archetype cards, side by side.
class ArchetypeGrid extends StatelessWidget {
  const ArchetypeGrid({
    super.key,
    required this.archetypes,
    required this.representatives,
  });

  final List<Archetype> archetypes;
  final SectionLoad<List<PlayerSummary>> Function(int clusterId)
  representatives;

  /// The key of the card surface for [clusterId], for tests.
  static Key cardKey(int clusterId) => ValueKey(('archetype-card', clusterId));

  static const double _gap = 20;
  static const double _padding = 20;

  @override
  Widget build(BuildContext context) {
    Widget row(Widget Function(Archetype archetype) cell) => IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (var i = 0; i < archetypes.length; i++) ...[
            if (i > 0) const SizedBox(width: _gap),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: _padding),
                child: cell(archetypes[i]),
              ),
            ),
          ],
        ],
      ),
    );
    return Stack(
      children: [
        // Stretch: the boxes have no child, so a loose height would leave
        // them zero tall.
        Positioned.fill(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              for (var i = 0; i < archetypes.length; i++) ...[
                if (i > 0) const SizedBox(width: _gap),
                Expanded(
                  child: Semantics(
                    container: true,
                    child: DecoratedBox(
                      key: cardKey(archetypes[i].clusterId),
                      decoration: BoxDecoration(
                        color: DelphosColors.surface,
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: DelphosColors.rule),
                      ),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(vertical: _padding),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            spacing: 16,
            children: [
              row((a) => ArchetypeTopLine(archetype: a)),
              row((a) => ArchetypeHeading(clusterId: a.clusterId)),
              row((a) => ArchetypePitch(clusterId: a.clusterId)),
              row((a) => ArchetypeMetrics(archetype: a)),
              row(
                (a) => Align(
                  alignment: Alignment.topLeft,
                  child: RepresentativeList(load: representatives(a.clusterId)),
                ),
              ),
              row(
                (a) => Align(
                  alignment: Alignment.bottomLeft,
                  child: TextLink(
                    label: 'Ver en el explorador',
                    onPressed: () => context.go(
                      ExplorerQuery(clusterId: a.clusterId).toLocation(),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
