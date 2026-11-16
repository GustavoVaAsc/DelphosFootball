// Tests for the shared pitch painter: the glyph variant drops the spots and
// the penalty and corner arcs that the banner variant keeps.
import 'package:delphos_frontend/ui/core/widgets/pitch_painter.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  const zone = Rect.fromLTWH(10, 5, 8, 8);
  final key = GlobalKey();

  Future<RenderObject> pumpPainter(
    WidgetTester tester,
    PitchPainter painter,
    Size size,
  ) async {
    await tester.pumpWidget(
      Directionality(
        textDirection: TextDirection.ltr,
        child: Center(
          child: CustomPaint(key: key, size: size, painter: painter),
        ),
      ),
    );
    return tester.renderObject(find.byKey(key));
  }

  testWidgets('the glyph draws the areas and goals, no arcs or spots', (
    tester,
  ) async {
    final glyph = await pumpPainter(
      tester,
      const PitchPainter.glyph(zone),
      const Size(36, 24),
    );
    // Outline, two penalty areas, two goal areas and two goals.
    expect(glyph, paintsExactlyCountTimes(#drawRect, 7));
    expect(glyph, paintsExactlyCountTimes(#drawArc, 0));
    // The centre circle only.
    expect(glyph, paintsExactlyCountTimes(#drawCircle, 1));
  });

  testWidgets('the banner adds spots, penalty arcs and corner arcs', (
    tester,
  ) async {
    final banner = await pumpPainter(
      tester,
      const PitchPainter.banner(zone, [(120, 77.5, 5)]),
      const Size(240, 155),
    );
    // Two penalty arcs and four corner arcs.
    expect(banner, paintsExactlyCountTimes(#drawArc, 6));
    // Centre circle, three spots and one player dot.
    expect(banner, paintsExactlyCountTimes(#drawCircle, 5));
  });
}
