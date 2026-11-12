/// The painted track of the valuation dumbbell: a 1 px axis in
/// `--pitch-line`, the 4 px gap between the two figures in the verdict's
/// colour, the market dot (ink-2 with a surface ring) and the hollow
/// estimate dot (3 px ink ring), as in the design preview.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';

/// Draws the axis, the verdict-coloured gap and the two dots on a track of
/// the given size; [market] and [estimate] are positions in 0..1.
class DumbbellPainter extends CustomPainter {
  const DumbbellPainter({
    required this.market,
    required this.estimate,
    required this.gapColour,
  });

  final double market;
  final double estimate;
  final Color gapColour;

  @override
  void paint(Canvas canvas, Size size) {
    final y = size.height / 2;
    final mx = market * size.width;
    final ex = estimate * size.width;
    canvas.drawRect(
      Rect.fromLTWH(0, y - 0.5, size.width, 1),
      Paint()..color = DelphosColors.pitchLine,
    );
    final left = mx < ex ? mx : ex;
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(left, y - 2, (ex - mx).abs(), 4),
        const Radius.circular(2),
      ),
      Paint()..color = gapColour,
    );
    // Market: an ink-2 dot with a surface ring and a hairline outline.
    canvas.drawCircle(Offset(mx, y), 6, Paint()..color = DelphosColors.ink2);
    canvas.drawCircle(Offset(mx, y), 5, Paint()..color = DelphosColors.surface);
    canvas.drawCircle(Offset(mx, y), 3, Paint()..color = DelphosColors.ink2);
    // Estimate: a hollow dot with a 3 px ink ring.
    canvas.drawCircle(Offset(ex, y), 6, Paint()..color = DelphosColors.ink);
    canvas.drawCircle(Offset(ex, y), 3, Paint()..color = DelphosColors.surface);
  }

  @override
  bool shouldRepaint(DumbbellPainter old) =>
      old.market != market ||
      old.estimate != estimate ||
      old.gapColour != gapColour;
}
