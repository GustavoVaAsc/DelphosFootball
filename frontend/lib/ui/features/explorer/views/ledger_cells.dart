/// The value cells of a table row: Edad, Posición, Mercado, Valor estimado
/// and Brecha (DESIGN.md §4). Kept together because they are one row's
/// figure rules; a missing estimate or age prints "N/D" in muted ink, with
/// no verdict colour and no ratio.
library;

import 'package:material_ui/material_ui.dart';

import '../../../../domain/models/player_summary.dart';
import '../../../../domain/models/valuation_status.dart';
import '../../../core/format/format.dart';
import '../../../core/labels/positions.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/pitch_glyph.dart';
import '../../../core/widgets/status_pill.dart';

/// Builders for one row's value cells.
abstract final class LedgerCells {
  static final TextStyle _missing = DelphosText.ui(
    color: DelphosColors.ink3,
    tabular: true,
  );

  /// Whole years; never rounded up.
  static Widget age(double? age) => Text(
    age == null ? notAvailable : formatNumber(age.floor()),
    style: age == null ? _missing : DelphosText.ui(tabular: true),
  );

  /// The pitch glyph and the sub-position; the broad line is in a tooltip,
  /// since the glyph already shows it.
  static Widget position(PlayerSummary p) => Row(
    spacing: 9,
    children: [
      PitchGlyph(position: p.position, subPosition: p.subPosition),
      Flexible(
        child: Tooltip(
          message: positionLabel(p.position) ?? '',
          excludeFromSemantics: true,
          child: Text(
            roleLabel(position: p.position, subPosition: p.subPosition) ?? '',
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: DelphosText.ui(weight: FontWeight.w500, height: 1.25),
          ),
        ),
      ),
    ],
  );

  static Widget market(double? value) =>
      Text(formatEur(value), style: DelphosText.condensed());

  /// The estimate takes the verdict's colour, never the raw gap's
  /// (DESIGN.md §2): one verdict per player.
  static Widget estimate(double? value, ValuationStatus? status) => Text(
    formatEur(value),
    style: value == null
        ? _missing
        : DelphosText.condensed(
            color: switch (status) {
              ValuationStatus.undervalued => DelphosColors.up,
              ValuationStatus.overvalued => DelphosColors.down,
              _ => DelphosColors.ink,
            },
          ),
  );

  /// The verdict pill over the estimate-to-price ratio ("1,3x").
  static Widget gap(PlayerSummary p) {
    final status = p.valuationStatus;
    final estimate = p.fairValueEur;
    final market = p.marketValueEur;
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      crossAxisAlignment: CrossAxisAlignment.end,
      spacing: 3,
      children: [
        if (status != null) StatusPill(status: status),
        if (estimate != null && market != null && market > 0)
          Text(
            formatMultiple(estimate / market),
            style: DelphosText.ui(
              size: TypeScale.secondary,
              color: DelphosColors.ink2,
              tabular: true,
            ),
          ),
      ],
    );
  }
}
