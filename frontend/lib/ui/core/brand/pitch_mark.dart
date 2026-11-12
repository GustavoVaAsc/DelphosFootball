/// The brand mark of the sidebar: the pitch glyph of the design preview
/// (a rectangle, the halfway line and the centre circle), drawn in code so
/// the app needs no icon library.
library;

import 'package:flutter/widgets.dart';

import '../theme/delphos_colors.dart';

/// The 32 px brand tile with the 18 px pitch glyph.
class PitchMark extends StatelessWidget {
  const PitchMark({super.key});

  @override
  Widget build(BuildContext context) {
    return ExcludeSemantics(
      child: Container(
        width: 32,
        height: 32,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: DelphosColors.sidebarMarkBorder),
        ),
        child: const CustomPaint(
          size: Size.square(18),
          painter: _PitchGlyphPainter(),
        ),
      ),
    );
  }
}

/// Paints the preview's 24-unit SVG (`rect 2,4 20x16 rx 2`, `line x=12`,
/// `circle r=3`) scaled to the canvas, stroke width 2 units.
class _PitchGlyphPainter extends CustomPainter {
  const _PitchGlyphPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final unit = size.width / 24;
    final paint = Paint()
      ..color = DelphosColors.onSidebar
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2 * unit;
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(2 * unit, 4 * unit, 20 * unit, 16 * unit),
        Radius.circular(2 * unit),
      ),
      paint,
    );
    canvas.drawLine(
      Offset(12 * unit, 4 * unit),
      Offset(12 * unit, 20 * unit),
      paint,
    );
    canvas.drawCircle(Offset(12 * unit, 12 * unit), 3 * unit, paint);
  }

  @override
  bool shouldRepaint(_PitchGlyphPainter oldDelegate) => false;
}
