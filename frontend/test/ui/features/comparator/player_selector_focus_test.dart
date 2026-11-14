// Widget tests for the comparator selector's keyboard contract (DESIGN.md
// §4): focus stays in the field while the suggestions load and change,
// typing keeps working, Down and Enter pick, and Escape closes the list
// first and keeps focus in the field.
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';

EditableText field(WidgetTester tester) =>
    tester.widget<EditableText>(find.byType(EditableText));

/// The ids of the field's semantics node and all of its ancestors.
List<int> fieldChain(WidgetTester tester) {
  final ids = <int>[];
  for (
    SemanticsNode? n = tester.getSemantics(find.byType(TextField));
    n != null;
    n = n.parent
  ) {
    ids.add(n.id);
  }
  return ids;
}

Future<GoRouter> focusedSelector(WidgetTester tester) async {
  final router = await pumpAppAt(tester, '/comparador');
  await tester.tap(find.byType(TextField));
  await tester.pump();
  expect(field(tester).focusNode.hasFocus, isTrue);
  return router;
}

Future<void> typeKeys(WidgetTester tester, String text) async {
  await tester.enterText(find.byType(TextField), text);
  await tester.pump();
}

Future<void> loadSuggestions(WidgetTester tester) async {
  await tester.pump(const Duration(milliseconds: 350));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('the field keeps its place in the semantics tree', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    await focusedSelector(tester);
    final before = fieldChain(tester);
    await typeKeys(tester, 'Pe');
    await tester.pump(const Duration(milliseconds: 350));
    expect(fieldChain(tester), before);
    await tester.pumpAndSettle();
    expect(find.text('Pe 501001'), findsOneWidget);
    expect(fieldChain(tester), before);
    handle.dispose();
  });

  testWidgets('focus stays in the field when the suggestions load', (
    tester,
  ) async {
    await focusedSelector(tester);
    await typeKeys(tester, 'Pe');
    await tester.pump(const Duration(milliseconds: 350));
    expect(field(tester).focusNode.hasFocus, isTrue);
    await tester.pumpAndSettle();
    expect(find.text('Pe 501001'), findsOneWidget);
    expect(field(tester).focusNode.hasFocus, isTrue);
  });

  testWidgets('a character typed after the load is appended', (tester) async {
    await focusedSelector(tester);
    await typeKeys(tester, 'Pe');
    await loadSuggestions(tester);
    tester.testTextInput.enterText('Ped');
    await tester.pump();
    expect(field(tester).controller.text, 'Ped');
    expect(field(tester).focusNode.hasFocus, isTrue);
  });

  testWidgets('Down and Enter pick the highlighted suggestion', (tester) async {
    final router = await focusedSelector(tester);
    await typeKeys(tester, 'Pe');
    await loadSuggestions(tester);
    await tester.sendKeyEvent(LogicalKeyboardKey.arrowDown);
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pumpAndSettle();
    expect(
      router.routerDelegate.currentConfiguration.uri.path,
      '/comparador/501001',
    );
  });

  testWidgets('Escape closes the list and keeps focus in the field', (
    tester,
  ) async {
    final router = await focusedSelector(tester);
    await typeKeys(tester, 'Pe');
    await loadSuggestions(tester);
    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pumpAndSettle();
    expect(find.text('Pe 501001'), findsNothing);
    expect(field(tester).focusNode.hasFocus, isTrue);
    expect(router.routerDelegate.currentConfiguration.uri.path, '/comparador');
  });
}
