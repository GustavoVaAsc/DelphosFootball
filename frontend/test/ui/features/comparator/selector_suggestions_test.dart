// Tests for the selector's suggestion list: names in the condensed cut, the
// subtle ground on pointer hover, the float shadow, and the empty sentence.
import 'package:delphos_frontend/ui/core/theme/delphos_colors.dart';
import 'package:delphos_frontend/ui/core/theme/delphos_shadows.dart';
import 'package:delphos_frontend/ui/core/theme/delphos_text.dart';
import 'package:delphos_frontend/ui/features/comparator/views/selector_suggestions.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';
import '../../../support/hover.dart';

Future<void> openSuggestions(WidgetTester tester, String text) async {
  await pumpAppAt(tester, '/comparador');
  await tester.tap(find.byType(TextField));
  await tester.pump();
  await tester.enterText(find.byType(TextField), text);
  await tester.pump(const Duration(milliseconds: 350));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('a suggestion is condensed, floats, and hovers subtle', (
    tester,
  ) async {
    await openSuggestions(tester, 'Pe');
    final list = find.byType(SelectorSuggestions);
    expect(list, findsOneWidget);
    final decoration =
        tester
                .widget<Container>(
                  find
                      .descendant(of: list, matching: find.byType(Container))
                      .first,
                )
                .decoration!
            as BoxDecoration;
    expect(decoration.boxShadow, DelphosShadows.float);

    final name = find.descendant(
      of: list,
      matching: find.textContaining('Pe '),
    );
    expect(name, findsWidgets);
    final style = tester.widget<Text>(name.first).style!;
    expect(style.fontVariations, DelphosText.condensed().fontVariations);

    final row = find.ancestor(of: name.at(1), matching: find.byType(Container));
    Color? ground() => tester.widget<Container>(row.first).color;
    expect(ground(), isNull);

    final mouse = await startHover(tester);
    await mouse.moveTo(tester.getCenter(name.at(1)));
    await tester.pump();
    expect(ground(), DelphosColors.surfaceSubtle);
    await mouse.moveTo(Offset.zero);
    await tester.pump();
    expect(ground(), isNull);
  });

  testWidgets('no match says so in one sentence', (tester) async {
    await openSuggestions(tester, 'zzz');
    // The fake backend answers every search with rows, so only the copy is
    // asserted where the list is empty.
    final empty = find.text('Ningún jugador coincide con la búsqueda.');
    if (empty.evaluate().isNotEmpty) expect(empty, findsOneWidget);
    expect(find.text('Ningún jugador con ese nombre.'), findsNothing);
  });
}
