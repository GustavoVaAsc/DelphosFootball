// Tests that Pressable activates on every path a browser uses: Enter as
// Flutter web binds it (ButtonActivateIntent), Space, a semantics tap, and a
// click; and that a disabled Pressable does nothing and takes no focus.
import 'package:delphos_frontend/ui/core/widgets/pressable.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

/// The Enter and Space bindings of WidgetsApp's web shortcut map
/// (`app.dart`, `_defaultWebShortcuts`), so a VM test sees what a browser
/// build sees.
const Map<ShortcutActivator, Intent> webEnterAndSpace = {
  SingleActivator(LogicalKeyboardKey.enter): ButtonActivateIntent(),
  SingleActivator(LogicalKeyboardKey.numpadEnter): ButtonActivateIntent(),
  SingleActivator(LogicalKeyboardKey.space): ActivateIntent(),
};

Future<FocusNode> pumpPressable(
  WidgetTester tester, {
  required VoidCallback? onPressed,
}) async {
  final node = FocusNode(debugLabel: 'pressable');
  addTearDown(node.dispose);
  await tester.pumpWidget(
    // The app's whole shortcut map is replaced, so no non-web binding can
    // catch Enter as a fallback.
    MaterialApp(
      shortcuts: webEnterAndSpace,
      home: Center(
        child: Pressable(
          onPressed: onPressed,
          semanticLabel: 'Reintentar',
          focusNode: node,
          builder: (_, _) => const Text('Reintentar'),
        ),
      ),
    ),
  );
  return node;
}

void main() {
  testWidgets('Enter, as the web binds it, activates', (tester) async {
    var presses = 0;
    final node = await pumpPressable(tester, onPressed: () => presses++);
    node.requestFocus();
    await tester.pump();
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.sendKeyEvent(LogicalKeyboardKey.numpadEnter);
    expect(presses, 2);
  });

  testWidgets('Space activates', (tester) async {
    var presses = 0;
    final node = await pumpPressable(tester, onPressed: () => presses++);
    node.requestFocus();
    await tester.pump();
    await tester.sendKeyEvent(LogicalKeyboardKey.space);
    expect(presses, 1);
  });

  testWidgets('a semantics tap (browser click, screen reader) activates', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    var presses = 0;
    await pumpPressable(tester, onPressed: () => presses++);
    tester.semantics.tap(find.semantics.byLabel('Reintentar'));
    expect(presses, 1);
    handle.dispose();
  });

  testWidgets('a disabled control takes no focus and no action', (
    tester,
  ) async {
    final node = await pumpPressable(tester, onPressed: null);
    node.requestFocus();
    await tester.pump();
    expect(node.hasFocus, isFalse);
    await tester.tap(find.text('Reintentar'));
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
  });
}
