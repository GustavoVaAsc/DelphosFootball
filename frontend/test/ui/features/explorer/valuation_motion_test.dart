// Tests for the valuation motion (DESIGN.md §5): the two figures count up
// each time a valuation loads, never on a rebuild.
import 'package:delphos_frontend/domain/models/player_valuation.dart';
import 'package:delphos_frontend/domain/models/valuation_status.dart';
import 'package:delphos_frontend/ui/core/format/money.dart';
import 'package:delphos_frontend/ui/features/explorer/views/valuation_section.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

PlayerValuation valuation(int id) => PlayerValuation(
  playerId: id,
  season: 2025,
  marketValueEur: 200e6,
  fairValueEur: 69.7e6,
  status: ValuationStatus.overvalued,
  rfUndervaluedProb: 0.1,
  rfUndervaluedPred: false,
  dtUndervaluedPred: false,
  modelRunId: 'run_test',
);

Widget host(PlayerValuation v, {required Key key}) => MediaQuery(
  data: const MediaQueryData(size: Size(440, 800)),
  child: Directionality(
    textDirection: TextDirection.ltr,
    child: Align(
      alignment: Alignment.topLeft,
      child: SizedBox(
        width: 400,
        child: ValuationSection(key: key, valuation: v),
      ),
    ),
  ),
);

void main() {
  final market = formatEur(200e6);
  final estimate = formatEur(69.7e6);
  final zero = formatEur(0);

  testWidgets('the figures count up once per loaded valuation', (tester) async {
    await tester.pumpWidget(host(valuation(1), key: const ValueKey(1)));
    expect(find.text(zero), findsNWidgets(2));

    await tester.pump(const Duration(milliseconds: 150));
    expect(find.text(zero), findsNothing);
    expect(find.text(estimate), findsNothing);

    await tester.pumpAndSettle();
    expect(find.text(market), findsOneWidget);
    expect(find.text(estimate), findsOneWidget);

    // A rebuild with the same player replays nothing.
    await tester.pumpWidget(host(valuation(1), key: const ValueKey(1)));
    expect(find.text(zero), findsNothing);
    expect(find.text(estimate), findsOneWidget);
    expect(tester.hasRunningAnimations, isFalse);

    // Another valuation loading plays it again.
    await tester.pumpWidget(host(valuation(2), key: const ValueKey(2)));
    expect(find.text(zero), findsNWidgets(2));
    await tester.pumpAndSettle();
    expect(find.text(estimate), findsOneWidget);
  });

  testWidgets('the status line is the word, a dot and the difference', (
    tester,
  ) async {
    await tester.pumpWidget(host(valuation(1), key: const ValueKey(1)));
    await tester.pumpAndSettle();
    expect(find.text('Sobrevalorado'), findsOneWidget);
    expect(find.text('·'), findsOneWidget);
    expect(find.textContaining('Diferencia'), findsOneWidget);
    expect(find.textContaining('−65%'), findsOneWidget);
  });
}
