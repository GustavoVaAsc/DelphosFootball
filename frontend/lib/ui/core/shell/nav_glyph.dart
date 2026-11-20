/// The stroke glyphs of the collapsed sidebar rail, one per module, and the
/// top bar's menu button. Drawn on a 24-unit box in the same line style
/// as `LineGlyph` (2-unit round strokes), because the app ships no icon font.
library;

import 'package:flutter/widgets.dart';

enum _Kind { explorer, comparator, archetypes, assistant, menu }

/// A decorative glyph; the control around it carries the label.
class NavGlyph extends StatelessWidget {
  /// A ledger: the Explorador de Mercado.
  const NavGlyph.explorer({super.key, required this.color, this.size = 20})
    : _kind = _Kind.explorer;

  /// Two opposed arrows: the Comparador Moneyball.
  const NavGlyph.comparator({super.key, required this.color, this.size = 20})
    : _kind = _Kind.comparator;

  /// Three groups: Arquetipos Tácticos.
  const NavGlyph.archetypes({super.key, required this.color, this.size = 20})
    : _kind = _Kind.archetypes;

  /// A speech bubble: PitIA, the scouting assistant.
  const NavGlyph.assistant({super.key, required this.color, this.size = 20})
    : _kind = _Kind.assistant;

  /// Three lines: the hamburger that folds and unfolds the sidebar.
  const NavGlyph.menu({super.key, required this.color, this.size = 20})
    : _kind = _Kind.menu;

  final Color color;
  final double size;
  final _Kind _kind;

  @override
  Widget build(BuildContext context) => ExcludeSemantics(
    child: CustomPaint(
      size: Size.square(size),
      painter: _NavGlyphPainter(kind: _kind, color: color),
    ),
  );
}

class _NavGlyphPainter extends CustomPainter {
  const _NavGlyphPainter({required this.kind, required this.color});

  final _Kind kind;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final u = size.width / 24;
    Offset at(double x, double y) => Offset(x * u, y * u);
    Path path(List<(double, double)> points) {
      final result = Path()..moveTo(points.first.$1 * u, points.first.$2 * u);
      for (final (x, y) in points.skip(1)) {
        result.lineTo(x * u, y * u);
      }
      return result;
    }

    RRect box(double x, double y, double w, double h, double r) =>
        RRect.fromRectAndRadius(
          Rect.fromLTWH(x * u, y * u, w * u, h * u),
          Radius.circular(r * u),
        );

    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..strokeWidth = 2 * u;
    switch (kind) {
      case _Kind.explorer:
        canvas.drawRRect(box(3, 4, 18, 16, 2), paint);
        canvas.drawLine(at(3, 10), at(21, 10), paint);
        canvas.drawLine(at(10, 10), at(10, 20), paint);
      case _Kind.comparator:
        canvas.drawLine(at(4, 8), at(20, 8), paint);
        canvas.drawPath(path([(16, 4), (20, 8), (16, 12)]), paint);
        canvas.drawLine(at(20, 16), at(4, 16), paint);
        canvas.drawPath(path([(8, 12), (4, 16), (8, 20)]), paint);
      case _Kind.archetypes:
        canvas.drawCircle(at(7, 8), 3.5 * u, paint);
        canvas.drawCircle(at(17, 8), 3.5 * u, paint);
        canvas.drawCircle(at(12, 17), 3.5 * u, paint);
      case _Kind.assistant:
        canvas.drawRRect(box(3, 4, 18, 13, 2), paint);
        canvas.drawPath(path([(8, 17), (8, 21), (12.5, 17)]), paint);
      case _Kind.menu:
        for (final y in const [6.0, 12.0, 18.0]) {
          canvas.drawLine(at(4, y), at(20, y), paint);
        }
    }
  }

  @override
  bool shouldRepaint(_NavGlyphPainter oldDelegate) =>
      oldDelegate.kind != kind || oldDelegate.color != color;
}
