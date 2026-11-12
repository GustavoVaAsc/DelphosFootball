/// The body lines of the comparison table (DESIGN.md §4): the "Valoración"
/// group (price, estimate in each player's verdict colour, status pill,
/// saving against the reference with the reference's price ceiling, and
/// tactical similarity), then the season group from `seasonRows`. The price
/// row has no delta: every candidate is cheaper by construction and the
/// savings row states the difference.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/replacement.dart';
import '../../../../domain/models/valuation_status.dart';
import '../../../core/format/format.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/view_models/section_status.dart';
import '../../../core/widgets/status_pill.dart';
import '../view_models/comparator_view_model.dart';
import 'compare_cells.dart';
import 'compare_row.dart';
import 'compare_rules.dart';
import 'season_figures.dart';
import 'delta_tone.dart';

/// The lines under the column headers.
List<Widget> compareTableBody({
  required ComparatorViewModel vm,
  required List<Replacement> candidates,
  required int missingSlots,
  int? datasetSeason,
}) {
  final valuation = vm.valuation.value!;
  final reference = vm.reference.value!;
  Color tone(ValuationStatus? status) => switch (status) {
    ValuationStatus.undervalued => DelphosColors.up,
    ValuationStatus.overvalued => DelphosColors.down,
    _ => DelphosColors.ink,
  };
  CompareRow line(
    String label,
    Widget reference,
    Widget Function(Replacement c) cell, {
    bool last = false,
  }) => CompareRow(
    metric: Text(
      label,
      style: DelphosText.ui(weight: FontWeight.w500, color: DelphosColors.ink2),
    ),
    reference: reference,
    candidates: [for (final c in candidates) cell(c)],
    missingSlots: missingSlots,
    last: last,
  );
  Widget group(String title) => Container(
    color: DelphosColors.surfaceSubtle,
    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
    child: Semantics(
      header: true,
      child: Text(
        title,
        style: DelphosText.ui(
          size: TypeScale.secondary,
          weight: FontWeight.w600,
          color: DelphosColors.ink3,
        ),
      ),
    ),
  );

  final seasonYear = reference.season?.season ?? datasetSeason;
  final candidateFigures = [
    for (final c in candidates) seasonFigures(vm.candidate(c.playerId).value),
  ];
  final rows = seasonRows(seasonFigures(reference), candidateFigures);
  return [
    group('Valoración'),
    line(
      'Precio de mercado',
      CompareCells.figure(formatEur(valuation.marketValueEur)),
      (c) => CompareCells.figure(formatEur(c.marketValueEur)),
    ),
    line(
      'Valor estimado',
      CompareCells.figure(
        formatEur(valuation.fairValueEur),
        colour: tone(valuation.status),
      ),
      (c) => CompareCells.figure(
        formatEur(c.fairValueEur),
        colour: tone(c.status),
      ),
    ),
    line(
      'Estado',
      StatusPill(status: valuation.status),
      (c) => c.status == null
          ? CompareCells.note(notAvailable)
          : StatusPill(status: c.status!),
    ),
    line(
      'Ahorro frente a la referencia',
      CompareCells.note(priceCeilingNote(valuation.marketValueEur)),
      (c) => CompareCells.value((
        text: formatEur(c.savingsEur),
        delta: '(${formatPct(c.costRatio - 1)})',
        tone: DeltaTone.neutral,
      )),
    ),
    line(
      'Similitud táctica',
      CompareCells.note('No aplica'),
      (c) => CompareCells.plain(formatPct(c.similarity)),
    ),
    group(
      seasonYear == null
          ? 'Temporada'
          : 'Temporada ${formatSeason(seasonYear)}',
    ),
    for (var r = 0; r < rows.length; r++)
      CompareRow(
        metric: Text(
          rows[r].label,
          style: DelphosText.ui(
            weight: FontWeight.w500,
            color: DelphosColors.ink2,
          ),
        ),
        reference: switch (rows[r].reference) {
          final text? => CompareCells.plain(text),
          null => CompareCells.note('Sin datos de temporada'),
        },
        candidates: [
          for (var i = 0; i < candidates.length; i++)
            switch ((
              vm.candidate(candidates[i].playerId).status,
              rows[r].cells[i],
            )) {
              (SectionStatus.loading, _) => CompareCells.pending(),
              (_, final cell?) => CompareCells.value(cell),
              _ => CompareCells.note('Sin datos de temporada'),
            },
        ],
        missingSlots: missingSlots,
        last: r == rows.length - 1,
      ),
  ];
}
