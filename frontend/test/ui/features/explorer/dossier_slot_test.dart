// Tests for the dossier panel's entry and exit: it slides in with a fade,
// stays on screen with its content through the exit while the table keeps
// the open layout, then leaves; a filter, a player switch or an error during
// the exit never leaves stale or blank content behind.
import 'package:delphos_frontend/ui/features/explorer/views/dossier_panel.dart';
import 'package:delphos_frontend/ui/features/explorer/views/ledger_layout.dart';
import 'package:delphos_frontend/ui/features/explorer/views/section_skeleton.dart';
import 'package:delphos_frontend/ui/features/explorer/views/table_header.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../../support/app_harness.dart';
import '../../../support/explorer_harness.dart';

/// The Posición column's width, measured from its cell box in the header.
double positionWidth(WidgetTester tester) => tester
    .getSize(
      find.descendant(
        of: find.byType(TableHeader),
        matching: find.byKey(LedgerLayout.positionCellKey),
      ),
    )
    .width;

void main() {
  testWidgets('the panel slides in from the right and fades', (tester) async {
    final router = await pumpAppAt(tester, '/explorador');
    expect(find.byType(DossierPanel), findsNothing);

    router.go('/explorador?jugador=1000');
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 60));
    final entering = tester.getTopLeft(find.byType(DossierPanel)).dx;
    await tester.pumpAndSettle();
    final rest = tester.getTopLeft(find.byType(DossierPanel)).dx;
    expect(entering, greaterThan(rest));
    expect(entering - rest, lessThanOrEqualTo(16));
  });

  testWidgets('the panel keeps its content through the exit, then leaves', (
    tester,
  ) async {
    final router = await pumpAppAt(tester, '/explorador?jugador=1000');
    expect(find.byType(DossierPanel), findsOneWidget);

    router.go('/explorador');
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 80));
    expect(find.byType(DossierPanel), findsOneWidget);
    await tester.pumpAndSettle();
    expect(find.byType(DossierPanel), findsNothing);
  });

  testWidgets('the table takes its width back when the exit ends', (
    tester,
  ) async {
    final router = await pumpAppAt(tester, '/explorador?jugador=1000');
    expect(positionWidth(tester), closeTo(LedgerLayout.positionOpenWidth, 0.5));

    router.go('/explorador');
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 80));
    expect(
      positionWidth(tester),
      closeTo(LedgerLayout.positionOpenWidth, 0.5),
      reason: 'mid-exit',
    );
    await tester.pumpAndSettle();
    expect(
      positionWidth(tester),
      closeTo(LedgerLayout.positionClosedWidth, 0.5),
    );
  });

  testWidgets('a search during the exit does not blank the content', (
    tester,
  ) async {
    final router = await pumpAppAt(tester, '/explorador?jugador=1000');
    router.go('/explorador');
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    router.go('/explorador?q=Zed');
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.byType(DossierPanel), findsOneWidget);
    expect(find.byType(SectionSkeleton), findsNothing);

    await tester.pumpAndSettle();
    expect(find.byType(DossierPanel), findsNothing);
  });

  testWidgets('another player during the exit keeps the panel open', (
    tester,
  ) async {
    final router = await pumpAppAt(tester, '/explorador?jugador=1000');
    router.go('/explorador');
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    router.go('/explorador?jugador=1001');
    await tester.pumpAndSettle();
    expect(find.byType(DossierPanel), findsOneWidget);
    expect(find.byType(SectionSkeleton), findsNothing);
    expect(positionWidth(tester), closeTo(LedgerLayout.positionOpenWidth, 0.5));
  });

  testWidgets('the same player reopened during the exit is never cleared', (
    tester,
  ) async {
    final backend = FakePlayersBackend();
    final router = await pumpAppAt(
      tester,
      '/explorador?jugador=1000',
      backend: backend,
    );
    int fetches() =>
        backend.requests.where((uri) => uri.path == '/players/1000').length;
    final before = fetches();

    router.go('/explorador');
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 80));
    router.go('/explorador?jugador=1000');
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.byType(SectionSkeleton), findsNothing);

    await tester.pumpAndSettle();
    expect(find.byType(DossierPanel), findsOneWidget);
    expect(fetches(), before, reason: 'the view model was never cleared');
    expect(positionWidth(tester), closeTo(LedgerLayout.positionOpenWidth, 0.5));
  });

  testWidgets('reduced motion removes the panel at once', (tester) async {
    final router = await pumpAppAt(tester, '/explorador?jugador=1000');
    tester.platformDispatcher.accessibilityFeaturesTestValue =
        const FakeAccessibilityFeatures(disableAnimations: true);
    addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
    await tester.pump();

    router.go('/explorador');
    await tester.pump();
    await tester.pump();
    expect(find.byType(DossierPanel), findsNothing);
    expect(
      positionWidth(tester),
      closeTo(LedgerLayout.positionClosedWidth, 0.5),
    );
  });

  testWidgets('an error during the exit still clears the dossier', (
    tester,
  ) async {
    final backend = FakePlayersBackend();
    final router = await pumpAppAt(
      tester,
      '/explorador?jugador=1000',
      backend: backend,
    );
    int fetches() =>
        backend.requests.where((uri) => uri.path == '/players/1000').length;
    final before = fetches();

    // Closing with a search the server cannot answer: the slot unmounts for
    // the error panel, so its exit never reports back.
    backend.failNext = true;
    router.go('/explorador?q=zzz');
    await tester.pumpAndSettle();
    expect(
      find.text('No se pudo conectar con el servidor de datos'),
      findsOneWidget,
    );

    // Reopening the same player must load it again, not show stale data.
    router.go('/explorador?jugador=1000');
    await tester.pumpAndSettle();
    expect(find.byType(DossierPanel), findsOneWidget);
    expect(fetches(), greaterThan(before));
  });
}
