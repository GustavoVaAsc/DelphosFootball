// Tests for the review fixes: every pill fits the Brecha column and every
// word of a position label fits the Posición column (Archivo metrics); a
// mouse click shows no focus ring and Escape returns focus to the row name;
// a state panel's button hugs its label.
import 'package:delphos_frontend/domain/models/valuation_status.dart';
import 'package:delphos_frontend/ui/core/labels/positions.dart';
import 'package:delphos_frontend/ui/core/labels/valuation_labels.dart';
import 'package:delphos_frontend/ui/core/theme/delphos_text.dart';
import 'package:delphos_frontend/ui/core/theme/type_scale.dart';
import 'package:delphos_frontend/ui/core/widgets/action_button.dart';
import 'package:delphos_frontend/ui/core/widgets/focus_ring.dart';
import 'package:delphos_frontend/ui/core/widgets/state_panel.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';

double widthOf(String text, TextStyle style) => (TextPainter(
  text: TextSpan(text: text, style: style),
  textDirection: TextDirection.ltr,
)..layout()).width;

void main() {
  testWidgets('every pill fits the 128 px Brecha column', (tester) async {
    await loadArchivo();
    // 128 px minus 8 px cell side and 14 px row edge; 16 px pill padding.
    const room = 128 - 8 - 14 - 16;
    final style = DelphosText.ui(
      size: TypeScale.secondary,
      weight: FontWeight.w600,
      tabular: true,
    );
    for (final status in ValuationStatus.values) {
      final label = valuationStatusLabel(status);
      expect(widthOf(label, style), lessThan(room), reason: label);
    }
  });

  testWidgets('no position word is wider than the open Posición column', (
    tester,
  ) async {
    await loadArchivo();
    // 142 px minus 16 px of cell sides, the 36 px glyph and its 9 px gap.
    const room = 142 - 16 - 36 - 9;
    final style = DelphosText.ui(weight: FontWeight.w500, height: 1.25);
    const keys = [
      'Centre-Forward', 'Right Winger', 'Left Winger', 'Second Striker', //
      'Attacking Midfield', 'Central Midfield', 'Defensive Midfield',
      'Right Midfield', 'Left Midfield', 'Centre-Back', 'Right-Back',
      'Left-Back',
    ];
    final labels = [
      for (final key in keys) subPositionLabel(key)!,
      for (final key in const ['Attack', 'Midfield', 'Defender'])
        positionLabel(key)!,
    ];
    for (final word in labels.expand((label) => label.split(' '))) {
      expect(widthOf(word, style), lessThan(room), reason: word);
    }
  });

  testWidgets('a click shows no ring; Escape focuses the row name', (
    tester,
  ) async {
    await pumpAppAt(tester, '/explorador');
    await tester.tap(find.text('Jugador 1000'));
    await tester.pumpAndSettle();
    final visibleRings = find.byWidgetPredicate(
      (widget) => widget is FocusRing && widget.visible,
    );
    expect(visibleRings, findsNothing);
    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pumpAndSettle();
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'row name 1000');
  });

  testWidgets('a state panel button hugs its label', (tester) async {
    await loadArchivo();
    await tester.pumpWidget(
      MaterialApp(
        home: SizedBox(
          width: 480,
          child: StatePanel(
            title: 'Ningún jugador cumple estos filtros',
            text: 'Filtros activos: búsqueda «zzz».',
            action: ActionButton(
              label: 'Restablecer filtros',
              onPressed: () {},
            ),
          ),
        ),
      ),
    );
    expect(tester.getSize(find.byType(ActionButton)).width, lessThan(160));
  });
}
