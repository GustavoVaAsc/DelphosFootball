// Tests for TextLink: always underlined, in the control-border colour at
// rest and in ink on hover (as in the design preview).
import 'package:delphos_frontend/ui/core/theme/delphos_colors.dart';
import 'package:delphos_frontend/ui/core/widgets/text_link.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/hover.dart';

void main() {
  testWidgets('is underlined at rest and darkens on hover', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Center(
          child: TextLink(label: 'Ver', onPressed: () {}),
        ),
      ),
    );
    TextStyle style() => tester.widget<Text>(find.text('Ver')).style!;
    expect(style().decoration, TextDecoration.underline);
    expect(style().decorationColor, DelphosColors.controlBorder);

    final mouse = await startHover(tester);
    await mouse.moveTo(tester.getCenter(find.text('Ver')));
    await tester.pump();
    expect(style().decoration, TextDecoration.underline);
    expect(style().decorationColor, DelphosColors.ink);
  });
}
