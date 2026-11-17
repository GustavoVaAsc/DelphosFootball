// Tests for the review fixes: every status word fits the Brecha column,
// every word of a position label fits the Posición column, currency figures
// and headers fit Mercado and Valor estimado, the search placeholder fits
// SearchField on a single FilterBar row at 1440 px, a mouse click shows no
// focus ring and Escape returns focus to the row name, and a state panel's
// button hugs its label.
import 'package:delphos_frontend/domain/models/valuation_status.dart';
import 'package:delphos_frontend/ui/core/format/format.dart';
import 'package:delphos_frontend/ui/core/labels/positions.dart';
import 'package:delphos_frontend/ui/core/labels/valuation_labels.dart';
import 'package:delphos_frontend/ui/core/theme/delphos_text.dart';
import 'package:delphos_frontend/ui/core/theme/type_scale.dart';
import 'package:delphos_frontend/ui/core/widgets/action_button.dart';
import 'package:delphos_frontend/ui/core/widgets/focus_ring.dart';
import 'package:delphos_frontend/ui/core/widgets/pitch_glyph.dart';
import 'package:delphos_frontend/ui/core/widgets/state_panel.dart';
import 'package:delphos_frontend/ui/features/explorer/views/filter_bar.dart';
import 'package:delphos_frontend/ui/features/explorer/views/ledger_layout.dart';
import 'package:delphos_frontend/ui/features/explorer/views/player_row.dart';
import 'package:delphos_frontend/ui/features/explorer/views/search_field.dart';
import 'package:delphos_frontend/ui/features/explorer/views/table_header.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';

double widthOf(String text, TextStyle style) => (TextPainter(
  text: TextSpan(text: text, style: style),
  textDirection: TextDirection.ltr,
)..layout()).width;

void main() {
  testWidgets('every status word fits the 112 px Brecha column', (
    tester,
  ) async {
    await loadArchivo();
    // 112 px minus 8 px cell side and 14 px row edge; the word has no ground
    // and so no padding.
    const room = 112 - 8 - 14;
    final style = DelphosText.ui(
      size: TypeScale.secondary,
      weight: FontWeight.w600,
      tabular: true,
    );
    for (final status in ValuationStatus.values) {
      final label = valuationStatusLabel(status);
      expect(widthOf(label, style), lessThan(room), reason: label);
    }
  });

  testWidgets('Mercado and Valor estimado fit headers and €200,0 M figures', (
    tester,
  ) async {
    await loadArchivo();
    final header = DelphosText.ui(
      size: TypeScale.secondary,
      weight: FontWeight.w500,
    );
    final figure = DelphosText.condensed();
    expect(widthOf('Mercado', header), lessThan(88 - 16));
    expect(widthOf('€200,0 M', figure), lessThan(88 - 16));
    expect(widthOf('Valor estimado', header), lessThan(110 - 16));
    expect(widthOf('€199,9 M', figure), lessThan(110 - 16));
  });

  testWidgets('search placeholder fits and FilterBar stays one row at 1440', (
    tester,
  ) async {
    await pumpAppAt(tester, '/explorador');
    const fieldRoom = SearchField.width - 2 - 10 - 14 - 6;
    expect(
      widthOf('Buscar jugador, club o país', DelphosText.ui()),
      lessThan(fieldRoom),
    );
    final bar = find.byType(FilterBar);
    final searchBox = tester.getRect(find.byType(SearchField));
    final resetBtn = tester.getRect(
      find.descendant(of: bar, matching: find.text('Restablecer filtros')),
    );
    final archetypeDrop = tester.getRect(
      find.descendant(of: bar, matching: find.textContaining('Arquetipo')),
    );
    expect((archetypeDrop.center.dy - searchBox.center.dy).abs(), lessThan(8));
    expect((resetBtn.center.dy - searchBox.center.dy).abs(), lessThan(8));
  });

  testWidgets('no position word is wider than the open Posición column', (
    tester,
  ) async {
    await loadArchivo();
    // 142 px minus 16 px of cell sides, the 36 px glyph and its 9 px gap.
    const room = 142 - 16 - 36 - 9;
    final style = DelphosText.ui(weight: FontWeight.w500, height: 1.25);
    const keys = [
      'Centre-Forward', 'Right Winger', 'Left Winger', 'Second Striker', //
      'Attacking Midfield', 'Central Midfield', 'Defensive Midfield',
      'Right Midfield', 'Left Midfield', 'Centre-Back', 'Right-Back',
      'Left-Back',
    ];
    final labels = [
      for (final key in keys) subPositionLabel(key)!,
      for (final key in const ['Attack', 'Midfield', 'Defender'])
        positionLabel(key)!,
    ];
    for (final word in labels.expand((label) => label.split(' '))) {
      expect(widthOf(word, style), lessThan(room), reason: word);
    }
  });

  testWidgets('a click shows no ring; Escape focuses the row name', (
    tester,
  ) async {
    await pumpAppAt(tester, '/explorador');
    await tester.tap(find.text('Jugador 1000'));
    await tester.pumpAndSettle();
    final visibleRings = find.byWidgetPredicate(
      (widget) => widget is FocusRing && widget.visible,
    );
    expect(visibleRings, findsNothing);
    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pumpAndSettle();
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'row name 1000');
  });

  testWidgets('a state panel button hugs its label', (tester) async {
    await loadArchivo();
    await tester.pumpWidget(
      MaterialApp(
        home: SizedBox(
          width: 480,
          child: StatePanel(
            title: 'Ningún jugador cumple estos filtros',
            text: 'Filtros activos: búsqueda «zzz».',
            action: ActionButton(
              label: 'Restablecer filtros',
              onPressed: () {},
            ),
          ),
        ),
      ),
    );
    expect(tester.getSize(find.byType(ActionButton)).width, lessThan(160));
  });

  testWidgets(
    'Posición header centres while pitch glyphs align left and metrics centre',
    (tester) async {
      await pumpAppAt(tester, '/explorador');
      final header = find.byType(TableHeader);
      final posHeaderCell = find.descendant(
        of: header,
        matching: find.byKey(LedgerLayout.positionCellKey),
      );
      final posHeader = find.descendant(
        of: header,
        matching: find.text('Posición'),
      );
      expect(
        (tester.getCenter(posHeader).dx - tester.getCenter(posHeaderCell).dx)
            .abs(),
        lessThan(1.0),
        reason: 'Posición header label is centred in its column',
      );

      final firstRow = find.byType(PlayerRow).first;
      final firstRowPosCell = find.descendant(
        of: firstRow,
        matching: find.byKey(LedgerLayout.positionCellKey),
      );
      final pitch = find.descendant(
        of: firstRow,
        matching: find.byType(PitchGlyph),
      );
      expect(
        (tester.getTopLeft(pitch).dx -
                (tester.getTopLeft(firstRowPosCell).dx + 8.0))
            .abs(),
        lessThan(1.0),
        reason: 'Pitch glyph stays left-justified inside the Posición cell',
      );
      final allPitches = tester.widgetList<PitchGlyph>(find.byType(PitchGlyph));
      if (allPitches.length > 1) {
        final firstDx = tester.getTopLeft(pitch).dx;
        final secondPitch = find.byType(PitchGlyph).at(1);
        expect(
          (tester.getTopLeft(secondPitch).dx - firstDx).abs(),
          lessThan(1.0),
          reason: 'Every row pitch glyph shares the same left edge',
        );
      }

      final ageHeader = find.descendant(
        of: header,
        matching: find.text('Edad'),
      );
      final ageValue = find
          .descendant(of: firstRow, matching: find.text(notAvailable))
          .first;
      expect(
        (tester.getCenter(ageHeader).dx - tester.getCenter(ageValue).dx).abs(),
        lessThan(1.0),
      );
      expect(
        tester.getTopLeft(pitch).dx - tester.getTopRight(ageValue).dx,
        greaterThan(28),
        reason: 'Edad stays well clear of the pitch glyph',
      );
    },
  );
}
