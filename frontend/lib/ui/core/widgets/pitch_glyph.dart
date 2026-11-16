/// The 36 x 24 mini pitch of each table row (DESIGN.md §1): the player's
/// zone on a horizontal pitch, attacking to the right.
///
/// The pitch is the shared `PitchPainter` in its glyph variant (outline,
/// halfway line, centre circle, both penalty and goal areas and the goals
/// outside the goal lines, in `--pitch-line`), and the zone is ink at 16%
/// with an ink outline. No zone hues: where the zone sits already says what
/// it is.
library;

import 'package:flutter/widgets.dart';

import '../theme/delphos_colors.dart';
import '../theme/delphos_radius.dart';
import 'pitch_painter.dart';

/// A row's position glyph. Decorative: the label beside it says the same.
class PitchGlyph extends StatelessWidget {
  const PitchGlyph({super.key, required this.position, this.subPosition});

  final String position;
  final String? subPosition;

  static const Size size = Size(36, 24);

  /// The zone rectangle in the 36 x 24 box, as the design preview maps it:
  /// wingers and full-backs on their flank, centre-forwards and
  /// centre-backs in the middle, midfielders across the halfway line. The
  /// pitch itself spans about x 2.9 to 33.1 and y 2.2 to 21.8 in that box.
  static Rect zoneFor(String position, String? subPosition) {
    final sub = subPosition ?? '';
    final (x, y, w, h) = switch (position) {
      'Attack' when sub.contains('Left') => (22.5, 3.5, 10.0, 6.0),
      'Attack' when sub.contains('Right') => (22.5, 14.5, 10.0, 6.0),
      'Attack' => (22.5, 6.0, 10.0, 12.0),
      'Defender' when sub.contains('Right') => (3.5, 14.5, 10.0, 6.0),
      'Defender' when sub.contains('Left') => (3.5, 3.5, 10.0, 6.0),
      'Defender' => (3.5, 5.0, 9.0, 14.0),
      _ => (13.0, 4.0, 10.0, 16.0),
    };
    return Rect.fromLTWH(x, y, w, h);
  }

  @override
  Widget build(BuildContext context) {
    return ExcludeSemantics(
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: DelphosColors.surfaceSubtle,
          borderRadius: BorderRadius.circular(DelphosRadius.small),
        ),
        child: CustomPaint(
          size: size,
          painter: PitchPainter.glyph(zoneFor(position, subPosition)),
        ),
      ),
    );
  }
}
