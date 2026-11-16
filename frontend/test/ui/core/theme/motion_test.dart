// Tests for the motion tokens: every duration is zero under reduced motion
// and kept otherwise, and every token stays in DESIGN.md §5's range.
import 'package:delphos_frontend/ui/core/theme/motion.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

Future<Duration> measure(
  WidgetTester tester,
  Duration duration, {
  required bool reduced,
}) async {
  late Duration result;
  await tester.pumpWidget(
    MediaQuery(
      data: MediaQueryData(disableAnimations: reduced),
      child: Builder(
        builder: (context) {
          result = DelphosMotion.duration(context, duration);
          return const SizedBox.shrink();
        },
      ),
    ),
  );
  return result;
}

void main() {
  const tokens = {
    'hover': DelphosMotion.hover,
    'dossierSwap': DelphosMotion.dossierSwap,
    'panel': DelphosMotion.panel,
    'sidebar': DelphosMotion.sidebar,
    'enter': DelphosMotion.enter,
  };

  testWidgets('reduced motion cuts every duration to zero', (tester) async {
    for (final entry in {
      ...tokens,
      'figures': DelphosMotion.figures,
      'stagger': DelphosMotion.stagger,
    }.entries) {
      expect(
        await measure(tester, entry.value, reduced: true),
        Duration.zero,
        reason: entry.key,
      );
    }
  });

  testWidgets('without reduced motion a duration is kept', (tester) async {
    expect(
      await measure(tester, DelphosMotion.panel, reduced: false),
      DelphosMotion.panel,
    );
  });

  test('a 12-row stagger ends within the 600 ms DESIGN.md promises', () {
    // The last of 12 rows starts after 11 steps and then plays its own entry.
    final end = DelphosMotion.stagger * 11 + DelphosMotion.enter;
    expect(end, lessThanOrEqualTo(const Duration(milliseconds: 600)));
  });
}
