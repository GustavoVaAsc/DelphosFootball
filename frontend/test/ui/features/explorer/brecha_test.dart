// Tests for the Brecha column: the verdict word over the signed percentage
// of the estimate against the price, the same number the dossier prints in
// "Diferencia (…)", never a ratio like "0,3x".
import 'package:delphos_frontend/ui/features/explorer/views/player_row.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../../support/app_harness.dart';
import '../../../support/explorer_harness.dart';

void main() {
  testWidgets('the table and the dossier print the same percentage', (
    tester,
  ) async {
    // Row price 1e6 and estimate 2,6e6 give +160%, as the dossier fixture
    // (60e6 against 155,9e6) does.
    final backend = FakePlayersBackend()..rowFairValue = 2.6e6;
    await pumpAppAt(tester, '/explorador?jugador=1000', backend: backend);
    final row = find.ancestor(
      of: find.text('Jugador 1000'),
      matching: find.byType(PlayerRow),
    );
    final rowPct = find.descendant(
      of: row.first,
      matching: find.textContaining(RegExp(r'^[+−]?\d+(,\d)?%$')),
    );
    expect(rowPct, findsOneWidget);

    final difference = tester.widget<Text>(find.textContaining('Diferencia'));
    final inParentheses = RegExp(r'\((.+)\)$').firstMatch(difference.data!);
    expect(inParentheses, isNotNull);
    expect(tester.widget<Text>(rowPct).data, inParentheses!.group(1));
    expect(inParentheses.group(1), '+160%');
  });

  testWidgets('no row prints a ratio', (tester) async {
    final backend = FakePlayersBackend()..rowFairValue = 2.6e6;
    await pumpAppAt(tester, '/explorador', backend: backend);
    expect(find.textContaining(RegExp(r'\dx$')), findsNothing);
  });
}
