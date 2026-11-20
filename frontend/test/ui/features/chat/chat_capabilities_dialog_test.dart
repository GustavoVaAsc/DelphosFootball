// The capabilities pop-up: first visit only, focus handling and Escape.
import 'package:delphos_frontend/ui/features/chat/view_models/chat_intro_gate.dart';
import 'package:delphos_frontend/ui/features/chat/views/chat_capabilities_dialog.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';

const _title = '¿Qué puede hacer PitIA?';
const _trigger = 'Capacidades de PitIA';

bool _inDialog(FocusNode node) => node.ancestors.any(
  (n) => n is FocusScopeNode && n.debugLabel == 'chat pop-up',
);

void main() {
  setUp(ChatIntroGate.reset);

  testWidgets('opens by itself on the first visit only', (tester) async {
    final router = await pumpAppAt(tester, '/chat');
    expect(find.text(_title), findsOneWidget);

    await tester.tap(find.text('Entendido'));
    await tester.pumpAndSettle();
    router.go('/');
    await tester.pumpAndSettle();
    router.go('/chat');
    await tester.pumpAndSettle();

    expect(find.byType(ChatCapabilitiesDialog), findsNothing);
  });

  testWidgets('focuses the close button and traps Tab inside', (tester) async {
    await pumpAppAt(tester, '/chat');
    await tester.pump();

    expect(FocusManager.instance.primaryFocus!.debugLabel, 'chat pop-up close');
    for (var i = 0; i < 12; i++) {
      await tester.sendKeyEvent(LogicalKeyboardKey.tab);
      await tester.pump();
      expect(_inDialog(FocusManager.instance.primaryFocus!), isTrue);
    }
  });

  testWidgets('Escape closes it and focus returns to the trigger', (
    tester,
  ) async {
    await pumpAppAt(tester, '/chat');
    await tester.tap(find.text('Entendido'));
    await tester.pumpAndSettle();

    await tester.tap(find.text(_trigger));
    await tester.pumpAndSettle();
    expect(find.text(_title), findsOneWidget);
    expect(FocusManager.instance.primaryFocus!.debugLabel, 'chat pop-up close');

    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pumpAndSettle();

    expect(find.text(_title), findsNothing);
    expect(
      FocusManager.instance.primaryFocus,
      Focus.of(tester.element(find.text(_trigger))),
    );
  });
}
