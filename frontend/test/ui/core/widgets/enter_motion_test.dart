// Tests for the one-shot entry: it waits out its delay, then fades in once;
// it is instant under reduced motion and absent when not animated.
import 'package:delphos_frontend/ui/core/widgets/enter_motion.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

Widget host(Widget child, {bool reduced = false}) => MediaQuery(
  data: MediaQueryData(disableAnimations: reduced),
  child: Directionality(textDirection: TextDirection.ltr, child: child),
);

Finder get layer => find.descendant(
  of: find.byType(EnterMotion),
  matching: find.byType(Opacity),
);

double opacity(WidgetTester tester) => tester.widget<Opacity>(layer).opacity;

void main() {
  const child = SizedBox(width: 10, height: 10);

  testWidgets('waits out its delay, then fades in and stops', (tester) async {
    await tester.pumpWidget(
      host(
        const EnterMotion(
          delay: Duration(milliseconds: 100),
          offset: Offset(0, 4),
          child: child,
        ),
      ),
    );
    expect(opacity(tester), 0);
    await tester.pump(const Duration(milliseconds: 50));
    expect(opacity(tester), 0, reason: 'still in the delay');
    await tester.pump(const Duration(milliseconds: 150));
    expect(opacity(tester), inExclusiveRange(0, 1));
    await tester.pumpAndSettle();
    expect(opacity(tester), 1);
    expect(tester.hasRunningAnimations, isFalse, reason: 'never loops');
  });

  testWidgets('is instant under reduced motion', (tester) async {
    await tester.pumpWidget(
      host(
        const EnterMotion(delay: Duration(milliseconds: 100), child: child),
        reduced: true,
      ),
    );
    expect(opacity(tester), 1);
  });

  testWidgets('does nothing when not animated, and never starts later', (
    tester,
  ) async {
    await tester.pumpWidget(
      host(const EnterMotion(animate: false, child: child)),
    );
    expect(layer, findsNothing);
    await tester.pumpWidget(host(const EnterMotion(child: child)));
    expect(layer, findsNothing);
  });
}
