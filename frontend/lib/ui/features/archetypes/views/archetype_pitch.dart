/// The pitch banner of an archetype card (DESIGN.md §1 and §4): a full
/// pitch in `--pitch-line` (outline, halfway line, centre circle and spot,
/// penalty and goal areas at both ends), the archetype's zone in ink at 16%
/// with an ink outline, and three ink player dots, laid out as in the
/// preview's `CLUSTER_PITCH_LAYOUTS` on a 240 x 92 box. No zone hues.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';

/// The banner for one archetype. Decorative: the card's text says the same.
class ArchetypePitch extends StatelessWidget {
  const ArchetypePitch({super.key, required this.clusterId});

  final int clusterId;

  @override
  Widget build(BuildContext context) {
    return ExcludeSemantics(
      child: Container(
        height: 112,
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: DelphosColors.surfaceSubtle,
          borderRadius: BorderRadius.circular(8),
        ),
        child: FittedBox(
          child: CustomPaint(
            size: const Size(240, 92),
            painter: _BannerPainter(_layouts[clusterId] ?? _layouts[2]!),
          ),
        ),
      ),
    );
  }

  /// Zone (x, y, w, h) and player dots (x, y, r), from the preview.
  static const Map<int, (Rect, List<(double, double, double)>)> _layouts = {
    0: (
      Rect.fromLTWH(148, 12, 82, 68),
      [(195, 46, 5), (172, 24, 4), (172, 68, 4)],
    ),
    1: (
      Rect.fromLTWH(68, 10, 104, 72),
      [(120, 46, 5), (105, 20, 4), (135, 72, 4)],
    ),
    2: (
      Rect.fromLTWH(10, 14, 88, 64),
      [(42, 34, 4.5), (42, 58, 4.5), (76, 46, 4.5)],
    ),
  };
}

class _BannerPainter extends CustomPainter {
  const _BannerPainter(this.layout);

  final (Rect, List<(double, double, double)>) layout;

  @override
  void paint(Canvas canvas, Size size) {
    final lines = Paint()
      ..color = DelphosColors.pitchLine
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2;
    final pitch = RRect.fromRectAndRadius(
      const Rect.fromLTWH(4, 4, 232, 84),
      const Radius.circular(4),
    );
    canvas.drawRRect(pitch, Paint()..color = DelphosColors.surface);
    canvas.drawRRect(pitch, lines);
    canvas.drawLine(const Offset(120, 4), const Offset(120, 88), lines);
    canvas.drawCircle(const Offset(120, 46), 18, lines);
    canvas.drawCircle(
      const Offset(120, 46),
      1.5,
      Paint()..color = DelphosColors.pitchLine,
    );
    for (final box in const [
      Rect.fromLTWH(4, 22, 30, 48),
      Rect.fromLTWH(206, 22, 30, 48),
      Rect.fromLTWH(4, 34, 11, 24),
      Rect.fromLTWH(225, 34, 11, 24),
    ]) {
      canvas.drawRect(box, lines);
    }
    final (zone, players) = layout;
    final zoneShape = RRect.fromRectAndRadius(zone, const Radius.circular(4));
    canvas.drawRRect(zoneShape, Paint()..color = DelphosColors.pitchZoneFill);
    canvas.drawRRect(
      zoneShape,
      Paint()
        ..color = DelphosColors.ink
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.3,
    );
    final dot = Paint()..color = DelphosColors.ink;
    for (final (x, y, r) in players) {
      canvas.drawCircle(Offset(x, y), r, dot);
    }
  }

  @override
  bool shouldRepaint(_BannerPainter oldDelegate) =>
      oldDelegate.layout != layout;
}
