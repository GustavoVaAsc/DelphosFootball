/// The stroke glyphs the app draws itself (it ships no icon font): the
/// search magnifier, the close ×, the select chevron and the check mark, each
/// drawn on a 24-unit box like the design preview's SVGs.
library;

import 'package:flutter/widgets.dart';

import '../theme/delphos_colors.dart';

enum _Kind { search, close, chevronDown, check }

/// A decorative stroke glyph; the control around it carries the label.
class LineGlyph extends StatelessWidget {
  /// The search field's magnifier, 14 px in `--ink-3`.
  const LineGlyph.search({
    super.key,
    this.size = 14,
    this.color = DelphosColors.ink3,
  }) : _kind = _Kind.search;

  /// The dossier's close ×, 14 px in ink.
  const LineGlyph.close({
    super.key,
    this.size = 14,
    this.color = DelphosColors.ink,
  }) : _kind = _Kind.close;

  /// A select's open indicator, 14 px in `--ink-2`.
  const LineGlyph.chevronDown({
    super.key,
    this.size = 14,
    this.color = DelphosColors.ink2,
  }) : _kind = _Kind.chevronDown;

  /// A finished step's check mark, 12 px in `--ink-3`.
  const LineGlyph.check({
    super.key,
    this.size = 12,
    this.color = DelphosColors.ink3,
  }) : _kind = _Kind.check;

  final double size;
  final Color color;
  final _Kind _kind;

  @override
  Widget build(BuildContext context) => ExcludeSemantics(
    child: CustomPaint(
      size: Size.square(size),
      painter: _GlyphPainter(kind: _kind, color: color),
    ),
  );
}

class _GlyphPainter extends CustomPainter {
  const _GlyphPainter({required this.kind, required this.color});

  final _Kind kind;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final u = size.width / 24;
    Offset at(double x, double y) => Offset(x * u, y * u);
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..strokeWidth = (kind == _Kind.close ? 2.4 : 2) * u;
    switch (kind) {
      case _Kind.search:
        canvas.drawCircle(at(11, 11), 8 * u, paint);
        canvas.drawLine(at(21, 21), at(16.65, 16.65), paint);
      case _Kind.close:
        canvas.drawLine(at(5, 5), at(19, 19), paint);
        canvas.drawLine(at(19, 5), at(5, 19), paint);
      case _Kind.chevronDown:
        canvas.drawPath(
          Path()
            ..moveTo(6 * u, 9 * u)
            ..lineTo(12 * u, 15 * u)
            ..lineTo(18 * u, 9 * u),
          paint,
        );
      case _Kind.check:
        canvas.drawPath(
          Path()
            ..moveTo(5 * u, 12.5 * u)
            ..lineTo(10 * u, 17.5 * u)
            ..lineTo(19 * u, 7 * u),
          paint,
        );
    }
  }

  @override
  bool shouldRepaint(_GlyphPainter oldDelegate) =>
      oldDelegate.kind != kind || oldDelegate.color != color;
}
