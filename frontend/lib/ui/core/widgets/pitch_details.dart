/// The fine markings of the pitch banner (DESIGN.md §1): centre and penalty
/// spots, penalty arcs and corner arcs. They are too small to render at the
/// 36 x 24 glyph, so only the banner draws them.
library;

import 'dart:math' as math;

import 'package:flutter/widgets.dart';

/// Paints the details on a [pitch] rect, [m] design units per metre.
abstract final class PitchDetails {
  static void paint(
    Canvas canvas, {
    required Rect pitch,
    required double m,
    required double stroke,
    required Paint lines,
    required Paint solid,
  }) {
    canvas.drawCircle(pitch.center, stroke * 1.6, solid);
    // The penalty arc is the part of the 9.15 m circle around the spot that
    // lies outside the box, whose edge is 5.5 m from the spot.
    final theta = math.acos(5.5 / 9.15);
    for (final left in const [true, false]) {
      final spot = Offset(
        left ? pitch.left + 11 * m : pitch.right - 11 * m,
        pitch.center.dy,
      );
      canvas.drawCircle(spot, stroke * 1.2, solid);
      canvas.drawArc(
        Rect.fromCircle(center: spot, radius: 9.15 * m),
        left ? -theta : math.pi - theta,
        2 * theta,
        false,
        lines,
      );
    }
    for (final (centre, start) in [
      (pitch.topLeft, 0.0),
      (pitch.topRight, math.pi / 2),
      (pitch.bottomRight, math.pi),
      (pitch.bottomLeft, 1.5 * math.pi),
    ]) {
      canvas.drawArc(
        Rect.fromCircle(center: centre, radius: 1.6 * m),
        start,
        math.pi / 2,
        false,
        lines,
      );
    }
  }
}
