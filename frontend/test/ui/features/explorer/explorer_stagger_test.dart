// Tests for the staggered first load of the table, on real animation state
// (the Opacity layers the entries paint with): the first rows enter once on
// the first load, and never on return, search or scroll.
import 'package:delphos_frontend/ui/core/widgets/enter_motion.dart';
import 'package:delphos_frontend/ui/features/explorer/views/player_row.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../../support/app_harness.dart';

/// The Opacity layers of the table's rows: only an entry that plays paints
/// one, and nothing else in the list does.
Finder get rowLayers =>
    find.descendant(of: find.byType(ListView), matching: find.byType(Opacity));

Future<void> pumpUntil(WidgetTester tester, Finder finder) async {
  for (var i = 0; i < 100 && finder.evaluate().isEmpty; i++) {
    await tester.pump(const Duration(milliseconds: 10));
  }
  expect(finder, findsWidgets);
}

void main() {
  testWidgets('the first rows stagger on the first load only', (tester) async {
    final router = await pumpAppAt(tester, '/explorador', settle: false);
    await pumpUntil(tester, find.byType(PlayerRow));
    await tester.pump(const Duration(milliseconds: 30));

    // At most 12 rows, still on their way in (30 ms apart).
    final layers = tester.widgetList<Opacity>(rowLayers).toList();
    expect(layers, isNotEmpty);
    expect(layers.length, lessThanOrEqualTo(12));
    expect(layers.any((layer) => layer.opacity < 1), isTrue);
    await tester.pumpAndSettle();
    expect(
      tester
          .widgetList<Opacity>(rowLayers)
          .every((layer) => layer.opacity == 1),
      isTrue,
    );

    router.go('/arquetipos');
    await tester.pumpAndSettle();
    router.go('/explorador');
    await tester.pump();
    await pumpUntil(tester, find.byType(PlayerRow));
    await tester.pump(const Duration(milliseconds: 30));
    expect(rowLayers, findsNothing, reason: 'returning does not animate');
  });

  testWidgets('searching does not stagger the new rows', (tester) async {
    final router = await pumpAppAt(tester, '/explorador');
    router.go('/explorador?q=Zed');
    await tester.pump();
    await pumpUntil(tester, find.textContaining('Zed'));
    await tester.pump(const Duration(milliseconds: 30));
    expect(rowLayers, findsNothing);
  });

  testWidgets('a row of the first set scrolled in later does not animate', (
    tester,
  ) async {
    await pumpAppAt(tester, '/explorador', settle: false);
    // A short window, set before the data arrives: the list builds the rows
    // in view plus its cache extent (about 250 px, which finders count as
    // offstage), and row 11 of the first 12 stays beyond both.
    tester.view.physicalSize = const Size(1440, 500);
    await pumpUntil(tester, find.byType(PlayerRow));
    expect(
      find.text('Jugador 1011', skipOffstage: false),
      findsNothing,
      reason: 'row 11 is not built in the first-load frame',
    );

    await tester.drag(find.byType(ListView).first, const Offset(0, -800));
    await tester.pump(const Duration(milliseconds: 30));

    final entry = find.ancestor(
      of: find.text('Jugador 1011'),
      matching: find.byWidgetPredicate(
        (widget) => widget is EnterMotion && widget.offset.dy == 6,
      ),
    );
    expect(entry, findsOneWidget);
    expect(tester.widget<EnterMotion>(entry).animate, isFalse);
    expect(
      find.descendant(of: entry, matching: find.byType(Opacity)),
      findsNothing,
    );
    await tester.pumpAndSettle();
  });
}
