/// The pitch banner of an archetype card (DESIGN.md §1 and §4): the shared
/// `PitchPainter` in its banner variant (every marking of the reference
/// pitch, goals outside the goal lines), the archetype's zone in ink at 16%
/// with an ink outline, and three ink player dots. The pitch keeps a real
/// 105:68 aspect ratio, centred on its ground at a capped width, instead of
/// stretching to the card. No zone hues.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_radius.dart';
import '../../../core/widgets/pitch_painter.dart';

/// The banner for one archetype. Decorative: the card's text says the same.
class ArchetypePitch extends StatelessWidget {
  const ArchetypePitch({super.key, required this.clusterId});

  final int clusterId;

  /// The widest the drawing grows, so it stays a diagram and not a poster.
  static const double _maxWidth = 264;

  @override
  Widget build(BuildContext context) {
    final (zone, players) = _layouts[clusterId] ?? _layouts[2]!;
    return ExcludeSemantics(
      child: Container(
        padding: const EdgeInsets.all(8),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: DelphosColors.surfaceSubtle,
          borderRadius: BorderRadius.circular(DelphosRadius.inset),
        ),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: _maxWidth),
          child: AspectRatio(
            aspectRatio: 240 / 155,
            child: CustomPaint(painter: PitchPainter.banner(zone, players)),
          ),
        ),
      ),
    );
  }

  /// Zone (x, y, w, h) and player dots (x, y, r) in the painter's 240 x 155
  /// design box, where the pitch spans x 6.5 to 233.5 and y 4 to 151: the
  /// preview's `CLUSTER_PITCH_LAYOUTS` re-mapped onto that pitch.
  static const Map<int, (Rect, List<(double, double, double)>)> _layouts = {
    0: (
      Rect.fromLTWH(147.5, 18, 80, 119),
      [(193, 77.5, 5), (171, 39, 4), (171, 116, 4)],
    ),
    1: (
      Rect.fromLTWH(69, 14.5, 102, 126),
      [(120, 77.5, 5), (105, 32, 4), (135, 123, 4)],
    ),
    2: (
      Rect.fromLTWH(12.5, 21.5, 86, 112),
      [(43.5, 56.5, 4.5), (43.5, 98.5, 4.5), (76.5, 77.5, 4.5)],
    ),
  };
}
