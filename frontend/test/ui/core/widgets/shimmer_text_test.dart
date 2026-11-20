// Tests for the thinking-label shimmer: it sweeps while animations are on,
// is plain static text under reduced motion, and leaves no ticker behind.
import 'package:delphos_frontend/ui/core/theme/delphos_colors.dart';
import 'package:delphos_frontend/ui/core/widgets/shimmer_text.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

Widget host(Widget child, {bool reduced = false}) => MediaQuery(
  data: MediaQueryData(disableAnimations: reduced),
  child: Directionality(textDirection: TextDirection.ltr, child: child),
);

const _label = ShimmerText(
  'Analizando tu petición…',
  style: TextStyle(color: DelphosColors.ink3, fontSize: 12),
);

void main() {
  testWidgets('sweeps a highlight over the letters while animations are on', (
    tester,
  ) async {
    await tester.pumpWidget(host(_label));

    expect(find.byType(ShaderMask), findsOneWidget);
    expect(find.text('Analizando tu petición…'), findsOneWidget);
    expect(tester.hasRunningAnimations, isTrue);

    // It loops: still running after more than one pass.
    await tester.pump(ShimmerText.period * 2);
    expect(tester.hasRunningAnimations, isTrue);
  });

  testWidgets('renders static text when animations are disabled', (
    tester,
  ) async {
    await tester.pumpWidget(host(_label, reduced: true));

    expect(find.byType(ShaderMask), findsNothing);
    expect(find.text('Analizando tu petición…'), findsOneWidget);
    expect(tester.hasRunningAnimations, isFalse);
  });

  testWidgets('stops when reduced motion is switched on', (tester) async {
    await tester.pumpWidget(host(_label));
    expect(tester.hasRunningAnimations, isTrue);

    await tester.pumpWidget(host(_label, reduced: true));
    expect(find.byType(ShaderMask), findsNothing);
    expect(tester.hasRunningAnimations, isFalse);
  });

  testWidgets('leaves no ticker running after it is removed', (tester) async {
    await tester.pumpWidget(host(_label));
    expect(tester.hasRunningAnimations, isTrue);

    await tester.pumpWidget(host(const SizedBox.shrink()));
    expect(tester.hasRunningAnimations, isFalse);
    expect(tester.binding.transientCallbackCount, 0);
  });
}
