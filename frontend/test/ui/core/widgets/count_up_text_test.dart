// Tests for the count-up figure: es-ES money on every frame, a fixed width,
// and the exact formatted value at the end (at once under reduced motion).
import 'package:delphos_frontend/ui/core/format/money.dart';
import 'package:delphos_frontend/ui/core/theme/delphos_text.dart';
import 'package:delphos_frontend/ui/core/widgets/count_up_text.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

Widget host({bool reduced = false}) => MediaQuery(
  data: MediaQueryData(disableAnimations: reduced),
  child: Directionality(
    textDirection: TextDirection.ltr,
    child: Align(
      alignment: Alignment.topLeft,
      child: CountUpText(
        value: 69700000,
        format: formatEur,
        style: DelphosText.condensed(),
      ),
    ),
  ),
);

String shown(WidgetTester tester) =>
    tester.widget<Text>(find.byType(Text)).data!;

void main() {
  final finalText = formatEur(69700000);

  testWidgets('counts up through the money formatter and lands exactly', (
    tester,
  ) async {
    await tester.pumpWidget(host());
    expect(shown(tester), formatEur(0));
    final width = tester.getSize(find.byType(CountUpText)).width;

    await tester.pump(const Duration(milliseconds: 150));
    final mid = shown(tester);
    expect(mid, isNot(finalText));
    expect(mid, isNot(formatEur(0)));
    expect(mid, startsWith('€'));
    expect(tester.getSize(find.byType(CountUpText)).width, width);

    await tester.pumpAndSettle();
    expect(shown(tester), finalText);
    expect(find.text(finalText), findsOneWidget);
  });

  testWidgets('shows the final value at once under reduced motion', (
    tester,
  ) async {
    await tester.pumpWidget(host(reduced: true));
    expect(shown(tester), finalText);
  });
}
