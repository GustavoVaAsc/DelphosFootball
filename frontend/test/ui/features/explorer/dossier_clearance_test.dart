// Tests for the dossier's spacing at the 440 px panel: the header's identity
// and definition lines start at least 8 px below the close button, which keeps
// its place at the top right, and the replacements action has room above and
// below it.
import 'package:delphos_frontend/ui/core/widgets/action_button.dart';
import 'package:delphos_frontend/ui/features/explorer/views/dossier_close_button.dart';
import 'package:delphos_frontend/ui/features/explorer/views/dossier_definition_row.dart';
import 'package:delphos_frontend/ui/features/explorer/views/dossier_header.dart';
import 'package:delphos_frontend/ui/features/explorer/views/dossier_identity_line.dart';
import 'package:delphos_frontend/ui/core/widgets/shrink_row.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../../support/app_harness.dart';

void main() {
  testWidgets('lines 2 and 3 start 8 px below the close button', (
    tester,
  ) async {
    await pumpAppAt(tester, '/explorador?jugador=1000');
    final close = tester.getRect(find.byType(DossierCloseButton));
    expect(close.size, const Size(32, 32));

    final name = tester.getRect(find.text('Jugador 1000').last);
    final identity = tester.getRect(find.byType(DossierIdentityLine));
    final definition = tester.getRect(find.byType(DossierDefinitionRow));
    expect(identity.top, greaterThanOrEqualTo(close.bottom + 8));
    expect(definition.top, greaterThan(identity.top));
    // The name keeps its reserved room beside the button.
    expect(name.right, lessThanOrEqualTo(close.left));
    // Line 2 is not narrowed to dodge the button: its available width is the
    // whole right column, so a short case is shown uncut, and it never
    // extends past the header's content edge.
    final header = tester.getRect(find.byType(DossierHeader));
    expect(identity.right, lessThanOrEqualTo(header.right));
    final row = tester.renderObject<RenderBox>(find.byType(ShrinkRow));
    expect(
      row.constraints.maxWidth,
      closeTo(header.right - identity.left, 0.5),
      reason: 'the row may use the whole right column',
    );
  });

  testWidgets('"Comparar reemplazos" has 12 px above and 16 px below', (
    tester,
  ) async {
    await pumpAppAt(tester, '/explorador?jugador=1000');
    final subtitle = tester.getRect(
      find.text('Mismo arquetipo y posición · ahorro ≥ 20%'),
    );
    final button = tester.getRect(
      find.ancestor(
        of: find.text('Comparar reemplazos'),
        matching: find.byType(ActionButton),
      ),
    );
    final firstRow = tester.getRect(find.text('Candidato 1'));
    expect(button.top - subtitle.bottom, closeTo(12, 0.5));
    expect(firstRow.top - button.bottom, greaterThanOrEqualTo(16));
  });
}
