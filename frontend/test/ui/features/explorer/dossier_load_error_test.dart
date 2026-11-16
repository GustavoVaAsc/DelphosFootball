// Tests for the dossier's part-level error: its "Reintentar" is a secondary
// button; only a whole-panel error keeps the primary one.
import 'package:delphos_frontend/ui/core/widgets/action_button.dart';
import 'package:delphos_frontend/ui/features/explorer/views/dossier_load_error.dart';
import 'package:delphos_frontend/ui/features/explorer/views/explorer_error_panel.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

void main() {
  testWidgets('the section retry is secondary, the panel retry primary', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Column(
          children: [
            DossierLoadError(onRetry: () {}),
            ExplorerErrorPanel(onRetry: () {}),
          ],
        ),
      ),
    );
    final buttons = tester
        .widgetList<ActionButton>(find.byType(ActionButton))
        .toList();
    expect(buttons, hasLength(2));
    expect(buttons[0].primary, isFalse);
    expect(buttons[1].primary, isTrue);
  });
}
