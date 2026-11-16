// Widget tests for the shell: the keyboard focus ring on the sidebar, the
// hamburger button at the top left of the sidebar that folds it, the browser
// tab title per module, and the es-ES locale.
import 'package:delphos_frontend/ui/core/shell/menu_button.dart';
import 'package:delphos_frontend/ui/core/shell/sidebar.dart';
import 'package:delphos_frontend/ui/core/shell/top_bar.dart';
import 'package:delphos_frontend/ui/core/theme/delphos_colors.dart';
import 'package:delphos_frontend/ui/core/widgets/focus_ring.dart';
import 'package:delphos_frontend/ui/core/widgets/pressable.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';

/// The tooltip with [message]. `find.byTooltip` looks for the Flutter
/// framework's `Tooltip`, which is not the `material_ui` one the app uses.
Finder tooltip(String message) => find.byWidgetPredicate(
  (widget) => widget is Tooltip && widget.message == message,
);

Finder visibleRing() =>
    find.byWidgetPredicate((widget) => widget is FocusRing && widget.visible);

/// The menu button while its ring is showing.
Finder get menuRing =>
    find.ancestor(of: visibleRing(), matching: find.byType(MenuButton));

/// Tabs until the ring is on the menu button (the first stop of the sidebar).
Future<void> tabToMenu(WidgetTester tester) async {
  for (var i = 0; i < 10 && menuRing.evaluate().isEmpty; i++) {
    await tester.sendKeyEvent(LogicalKeyboardKey.tab);
    await tester.pump();
  }
  expect(
    menuRing,
    findsOneWidget,
    reason:
        'focus: ${FocusManager.instance.primaryFocus}, '
        'rings: ${visibleRing().evaluate().length}',
  );
}

String documentTitle(WidgetTester tester) =>
    tester.widget<Title>(find.byType(Title).last).title;

void main() {
  final menu = find.byType(MenuButton);

  testWidgets('Tab starts on the menu button, then the items, in white', (
    tester,
  ) async {
    await pumpAppAt(tester, '/explorador');
    expect(visibleRing(), findsNothing);

    await tester.sendKeyEvent(LogicalKeyboardKey.tab);
    await tester.pump();
    expect(menuRing, findsOneWidget);
    expect(
      tester.widget<FocusRing>(visibleRing()).color,
      DelphosColors.onSidebar,
    );

    await tester.sendKeyEvent(LogicalKeyboardKey.tab);
    await tester.pump();
    final ring = tester.widget<FocusRing>(visibleRing());
    expect(ring.color, DelphosColors.onSidebar);
    expect(
      find.descendant(
        of: visibleRing(),
        matching: find.text('Explorador de Mercado'),
      ),
      findsOneWidget,
    );

    await tester.sendKeyEvent(LogicalKeyboardKey.tab);
    await tester.pump();
    expect(
      find.descendant(
        of: visibleRing(),
        matching: find.text('Comparador Moneyball'),
      ),
      findsOneWidget,
    );
  });

  testWidgets('Enter on a focused item navigates', (tester) async {
    await pumpAppAt(tester, '/explorador');
    // The menu button, then the first three items.
    for (var i = 0; i < 4; i++) {
      await tester.sendKeyEvent(LogicalKeyboardKey.tab);
    }
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pumpAndSettle();
    expect(documentTitle(tester), 'Arquetipos Tácticos · DelphosFootball');
  });

  testWidgets('the menu button folds the sidebar to a 64 px rail of icons', (
    tester,
  ) async {
    await pumpAppAt(tester, '/explorador');
    expect(tester.getSize(find.byType(Sidebar)).width, 240);
    expect(find.text('Plegar menú'), findsNothing, reason: 'not a text item');

    await tester.tap(menu);
    await tester.pumpAndSettle();

    expect(tester.getSize(find.byType(Sidebar)).width, 64);
    expect(
      find.descendant(
        of: find.byType(Sidebar),
        matching: find.text('Explorador de Mercado'),
      ),
      findsNothing,
    );
    expect(
      find.descendant(
        of: find.byType(Sidebar),
        matching: find.text('DelphosFootball'),
      ),
      findsNothing,
    );
    for (final label in [
      'Explorador de Mercado',
      'Comparador Moneyball',
      'Arquetipos Tácticos',
      'Asistente de Scouting',
      'Desplegar menú',
    ]) {
      expect(tooltip(label), findsOneWidget, reason: label);
    }
  });

  testWidgets('the button is in the sidebar header, not in the top bar', (
    tester,
  ) async {
    await pumpAppAt(tester, '/explorador');
    expect(
      find.descendant(of: find.byType(Sidebar), matching: menu),
      findsOneWidget,
    );
    expect(
      find.descendant(of: find.byType(TopBar), matching: menu),
      findsNothing,
    );
    expect(
      find.descendant(
        of: find.byType(Sidebar),
        matching: find.byType(Pressable),
      ),
      findsNWidgets(5),
      reason: 'the menu button and the four module links',
    );
    // The brand mark is gone: the button is the first thing in the header.
    expect(find.text('DelphosFootball'), findsOneWidget);
  });

  testWidgets('the sidebar width eases between 240 and 64 px', (tester) async {
    await pumpAppAt(tester, '/explorador');
    await tester.tap(menu);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 160));
    final mid = tester.getSize(find.byType(Sidebar)).width;
    expect(mid, inExclusiveRange(64, 240));
    await tester.pumpAndSettle();
    expect(tester.getSize(find.byType(Sidebar)).width, 64);
  });

  testWidgets('the menu button keeps focus and its ring while folding', (
    tester,
  ) async {
    await pumpAppAt(tester, '/explorador');
    await tabToMenu(tester);
    final focused = FocusManager.instance.primaryFocus;

    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    expect(
      tester.getSize(find.byType(Sidebar)).width,
      inExclusiveRange(64, 240),
    );
    expect(FocusManager.instance.primaryFocus, same(focused));
    expect(menuRing, findsOneWidget);
    await tester.pumpAndSettle();
  });

  testWidgets('the menu button never moves while the sidebar folds', (
    tester,
  ) async {
    await pumpAppAt(tester, '/explorador');
    Rect button() => tester.getRect(menu);
    final open = button();
    expect(open.size, const Size(36, 36));
    expect(open.center.dx, 32, reason: 'centred on the 64 px rail');

    await tester.tap(menu);
    await tester.pump();
    for (final ms in [40, 60, 60, 60]) {
      await tester.pump(Duration(milliseconds: ms));
      expect(button(), open, reason: 'mid-fold');
    }
    await tester.pumpAndSettle();
    expect(tester.getSize(find.byType(Sidebar)).width, 64);
    expect(button(), open, reason: 'folded');
  });

  // One test per page: `DelphosApp` keeps its first router, so pumping a
  // second location in the same test would still show the first page.
  for (final path in ['/explorador', '/comparador', '/arquetipos', '/chat']) {
    testWidgets('$path has the menu button in the sidebar only', (
      tester,
    ) async {
      await pumpAppAt(tester, path);
      expect(menu, findsOneWidget);
      expect(
        find.descendant(of: find.byType(Sidebar), matching: menu),
        findsOneWidget,
      );
      expect(
        find.descendant(of: find.byType(TopBar), matching: menu),
        findsNothing,
      );
    });
  }

  testWidgets('its label and state follow the sidebar', (tester) async {
    final semantics = tester.ensureSemantics();
    await pumpAppAt(tester, '/explorador');
    expect(find.bySemanticsLabel('Plegar menú'), findsOneWidget);
    expect(find.bySemanticsLabel('Desplegar menú'), findsNothing);

    await tester.tap(menu);
    await tester.pumpAndSettle();
    expect(find.bySemanticsLabel('Desplegar menú'), findsOneWidget);
    expect(find.bySemanticsLabel('Plegar menú'), findsNothing);
    semantics.dispose();
  });

  testWidgets('keyboard focus on the menu button shows its tooltip', (
    tester,
  ) async {
    await pumpAppAt(tester, '/explorador');
    expect(find.text('Plegar menú'), findsNothing);

    await tabToMenu(tester);
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.text('Plegar menú'), findsOneWidget);
    await tester.pumpAndSettle();
  });

  testWidgets('reduced motion folds the sidebar at once', (tester) async {
    await pumpAppAt(tester, '/explorador');
    tester.platformDispatcher.accessibilityFeaturesTestValue =
        const FakeAccessibilityFeatures(disableAnimations: true);
    addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
    await tester.pump();

    await tester.tap(menu);
    await tester.pump();
    expect(tester.getSize(find.byType(Sidebar)).width, 64);
  });

  testWidgets('keyboard focus on a rail icon shows its name', (tester) async {
    await pumpAppAt(tester, '/arquetipos');
    await tester.tap(menu);
    await tester.pumpAndSettle();
    // The top bar already shows this title once; the tooltip adds a second.
    final name = find.text('Arquetipos Tácticos');
    final before = name.evaluate().length;

    // The menu button, then the first three icons.
    for (var i = 0; i < 4; i++) {
      await tester.sendKeyEvent(LogicalKeyboardKey.tab);
      await tester.pump();
    }
    await tester.pump(const Duration(milliseconds: 100));
    expect(name.evaluate().length, before + 1);
    await tester.pumpAndSettle();
  });

  testWidgets('the rail navigates, keeps its state and unfolds by keyboard', (
    tester,
  ) async {
    final router = await pumpAppAt(tester, '/explorador');
    await tester.tap(menu);
    await tester.pumpAndSettle();

    await tester.tap(tooltip('Arquetipos Tácticos'));
    await tester.pumpAndSettle();
    expect(currentPath(router), '/arquetipos');
    expect(tester.getSize(find.byType(Sidebar)).width, 64);

    await tabToMenu(tester);
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pumpAndSettle();
    expect(tester.getSize(find.byType(Sidebar)).width, 240);
    expect(tooltip('Plegar menú'), findsOneWidget);
  });

  testWidgets('the not-found link shows the ink ring', (tester) async {
    await pumpAppAt(tester, '/no-existe');
    await tester.sendKeyEvent(LogicalKeyboardKey.tab);
    await tester.pump();
    expect(tester.widget<FocusRing>(visibleRing()).color, DelphosColors.ink);
  });

  const titles = {
    '/explorador': 'Explorador de Mercado · DelphosFootball',
    '/comparador/9': 'Comparador Moneyball · DelphosFootball',
    '/arquetipos': 'Arquetipos Tácticos · DelphosFootball',
    '/chat': 'Asistente de Scouting · DelphosFootball',
    '/no-existe': 'DelphosFootball · Dirección Deportiva',
  };
  titles.forEach((path, title) {
    testWidgets('$path sets the browser tab title', (tester) async {
      await pumpAppAt(tester, path);
      expect(documentTitle(tester), title);
    });
  });

  testWidgets('the app runs in es-ES with Spanish Material strings', (
    tester,
  ) async {
    await pumpAppAt(tester, '/explorador');
    final context = tester.element(find.text('Jugador'));
    expect(Localizations.localeOf(context), const Locale('es', 'ES'));
    expect(MaterialLocalizations.of(context).closeButtonTooltip, 'Cerrar');
  });
}
