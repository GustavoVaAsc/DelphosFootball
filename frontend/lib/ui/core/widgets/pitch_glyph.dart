/// The 36 x 24 mini pitch of each table row (DESIGN.md §1): the player's
/// zone on a horizontal pitch, attacking to the right.
///
/// The pitch is drawn in `--pitch-line` (outline, halfway line, centre
/// circle and both penalty boxes) and the zone is ink at 16% with an ink
/// outline. No zone hues: where the zone sits already says what it is.
library;

import 'package:flutter/widgets.dart';

import '../theme/delphos_colors.dart';

/// A row's position glyph. Decorative: the label beside it says the same.
class PitchGlyph extends StatelessWidget {
  const PitchGlyph({super.key, required this.position, this.subPosition});

  final String position;
  final String? subPosition;

  static const Size size = Size(36, 24);

  /// The zone rectangle in the 36 x 24 box, as the design preview maps it:
  /// wingers and full-backs on their flank, centre-forwards and
  /// centre-backs in the middle, midfielders across the halfway line.
  static Rect zoneFor(String position, String? subPosition) {
    final sub = subPosition ?? '';
    final (x, y, w, h) = switch (position) {
      'Attack' when sub.contains('Left') => (23.0, 2.0, 11.0, 7.0),
      'Attack' when sub.contains('Right') => (23.0, 15.0, 11.0, 7.0),
      'Attack' => (23.0, 6.0, 11.0, 12.0),
      'Defender' when sub.contains('Right') => (2.0, 15.0, 11.0, 7.0),
      'Defender' when sub.contains('Left') => (2.0, 2.0, 11.0, 7.0),
      'Defender' => (2.0, 5.0, 10.0, 14.0),
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
          borderRadius: BorderRadius.circular(3),
        ),
        child: CustomPaint(
          size: size,
          painter: _PitchPainter(zoneFor(position, subPosition)),
        ),
      ),
    );
  }
}

class _PitchPainter extends CustomPainter {
  const _PitchPainter(this.zone);

  final Rect zone;

  @override
  void paint(Canvas canvas, Size size) {
    final lines = Paint()
      ..color = DelphosColors.pitchLine
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.9;
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        const Rect.fromLTWH(1, 1, 34, 22),
        const Radius.circular(1.5),
      ),
      lines,
    );
    canvas.drawLine(const Offset(18, 1), const Offset(18, 23), lines);
    canvas.drawCircle(const Offset(18, 12), 3.2, lines);
    canvas.drawRect(const Rect.fromLTWH(1, 7, 5, 10), lines);
    canvas.drawRect(const Rect.fromLTWH(30, 7, 5, 10), lines);

    final zoneShape = RRect.fromRectAndRadius(zone, const Radius.circular(1.2));
    canvas.drawRRect(zoneShape, Paint()..color = DelphosColors.pitchZoneFill);
    canvas.drawRRect(
      zoneShape,
      Paint()
        ..color = DelphosColors.ink
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.1,
    );
  }

  @override
  bool shouldRepaint(_PitchPainter oldDelegate) => oldDelegate.zone != zone;
}
