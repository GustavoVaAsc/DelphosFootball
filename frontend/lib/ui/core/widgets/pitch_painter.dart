/// The one pitch drawing of the app, shared by the table's position glyph and
/// the Arquetipos banner (DESIGN.md §1): a horizontal 105 x 68 pitch seen
/// from above, attacking to the right, with the goals drawn outside the goal
/// lines, from the reference `cancha-referencia.png`.
///
/// Markings are `--pitch-line`; the zone is ink at 16% with an ink outline;
/// player dots are ink. No hues. The glyph variant drops what would render as
/// sub-pixel noise at 36 x 24 (spots, penalty arcs, corner arcs).
library;

import 'dart:math' as math;

import 'package:flutter/widgets.dart';

import '../theme/delphos_colors.dart';
import 'pitch_details.dart';

/// Paints the pitch, then [zone] and [players], in a [design]-sized box that
/// is scaled to the canvas (so the canvas must have the design's aspect).
class PitchPainter extends CustomPainter {
  const PitchPainter._({
    required this.zone,
    required this.players,
    required this.design,
    required this.detailed,
    required this.goalDepth,
    required this.stroke,
  });

  /// The 36 x 24 table glyph: markings only, plus the zone.
  const PitchPainter.glyph(Rect zone)
    : this._(
        zone: zone,
        players: const [],
        design: const Size(36, 24),
        detailed: false,
        goalDepth: 2,
        stroke: 0.9,
      );

  /// The Arquetipos banner: every marking, the zone and the player dots
  /// (x, y, radius), in a 240 x 155 design box.
  const PitchPainter.banner(Rect zone, List<(double, double, double)> players)
    : this._(
        zone: zone,
        players: players,
        design: const Size(240, 155),
        detailed: true,
        goalDepth: 5.3,
        stroke: 1,
      );

  final Rect zone;
  final List<(double, double, double)> players;
  final Size design;
  final bool detailed;

  /// How far the goals stand outside the goal lines, in design units.
  final double goalDepth;
  final double stroke;

  static const double _length = 105;
  static const double _width = 68;

  @override
  void paint(Canvas canvas, Size size) {
    canvas.scale(size.width / design.width, size.height / design.height);
    // The largest 105:68 pitch that leaves room for the goals and strokes.
    final room = Rect.fromLTRB(
      goalDepth + stroke,
      stroke,
      design.width - goalDepth - stroke,
      design.height - stroke,
    );
    final m = math.min(room.width / _length, room.height / _width);
    final pitch = Rect.fromCenter(
      center: room.center,
      width: _length * m,
      height: _width * m,
    );
    final lines = Paint()
      ..color = DelphosColors.pitchLine
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke;
    final solid = Paint()..color = DelphosColors.pitchLine;
    final cy = pitch.center.dy;

    // A box of [depth] x [span] metres on the goal line of one end.
    Rect box(double depth, double span, {required bool left}) => Rect.fromLTWH(
      left ? pitch.left : pitch.right - depth * m,
      cy - span * m / 2,
      depth * m,
      span * m,
    );

    if (detailed) {
      canvas.drawRect(pitch, Paint()..color = DelphosColors.surface);
    }
    canvas.drawRect(pitch, lines);
    canvas.drawLine(pitch.topCenter, pitch.bottomCenter, lines);
    canvas.drawCircle(pitch.center, 9.15 * m, lines);
    for (final left in const [true, false]) {
      canvas.drawRect(box(16.5, 40.32, left: left), lines);
      canvas.drawRect(box(5.5, 18.32, left: left), lines);
      final mouth = box(0, 7.32, left: left);
      canvas.drawRect(
        Rect.fromLTWH(
          left ? mouth.left - goalDepth : mouth.right,
          mouth.top,
          goalDepth,
          mouth.height,
        ),
        lines,
      );
    }
    if (detailed) {
      PitchDetails.paint(
        canvas,
        pitch: pitch,
        m: m,
        stroke: stroke,
        lines: lines,
        solid: solid,
      );
    }

    final shape = RRect.fromRectAndRadius(
      zone,
      Radius.circular(detailed ? 4 : 1.2),
    );
    canvas.drawRRect(shape, Paint()..color = DelphosColors.pitchZoneFill);
    canvas.drawRRect(
      shape,
      Paint()
        ..color = DelphosColors.ink
        ..style = PaintingStyle.stroke
        ..strokeWidth = detailed ? 1.3 : 1.1,
    );
    final ink = Paint()..color = DelphosColors.ink;
    for (final (x, y, r) in players) {
      canvas.drawCircle(Offset(x, y), r, ink);
    }
  }

  @override
  bool shouldRepaint(PitchPainter oldDelegate) =>
      oldDelegate.zone != zone ||
      oldDelegate.players != players ||
      oldDelegate.detailed != detailed;
}
