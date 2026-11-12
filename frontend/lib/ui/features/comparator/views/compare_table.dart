/// The comparison table (DESIGN.md §4, Comparador Moneyball): metrics as
/// rows, the reference first and up to three candidates as columns, in two
/// groups, "Valoración" and "Temporada 2025/26". With fewer than three
/// candidates one placeholder column states "N de 3 reemplazos" and why;
/// it is never a padded candidate. No "Resumen" here.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/replacement.dart';
import '../../../core/format/format.dart';
import '../../../core/labels/leagues.dart';
import '../../../core/labels/shortfall.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/view_models/section_status.dart';
import '../view_models/comparator_view_model.dart';
import 'compare_player_head.dart';
import 'compare_row.dart';
import 'compare_table_body.dart';

/// The table for a loaded reference.
class CompareTable extends StatelessWidget {
  const CompareTable({super.key, required this.vm, this.datasetSeason});

  final ComparatorViewModel vm;

  /// Titles the season group when the reference has no season row.
  final int? datasetSeason;

  @override
  Widget build(BuildContext context) {
    final reference = vm.reference.value!;
    final set = vm.replacements.value;
    final candidates = set?.candidates ?? const <Replacement>[];
    final missing = 3 - candidates.length;
    final slotText = switch (vm.replacements.status) {
      SectionStatus.absent => 'Este jugador no tiene reemplazos calculados.',
      _ when set == null => '',
      _ =>
        describeShortfall(
              qualifyingCount: set.qualifyingCount,
              reason: set.shortfallReason,
            ) ??
            'Ningún jugador cumple los criterios de reemplazo.',
    };
    final header = CompareRow(
      verticalPadding: 14,
      referenceGround: DelphosColors.surfaceMuted,
      missingSlots: missing,
      metric: Semantics(label: 'Métrica', child: const SizedBox.shrink()),
      reference: ComparePlayerHead(
        kicker: 'Referencia',
        isReference: true,
        eliteAsset: set?.isEliteAsset ?? false,
        name: reference.name,
        imageUrl: reference.imageUrl,
        crestUrl: reference.clubLogoUrl,
        country: reference.country,
        club: reference.clubName,
        league: leagueLabel(reference.season?.leagueId),
      ),
      candidates: [
        for (final c in candidates)
          ComparePlayerHead(
            kicker: 'Reemplazo ${formatNumber(c.rank)}',
            name: c.name,
            imageUrl: c.imageUrl,
            crestUrl: c.clubLogoUrl,
            country: c.country,
            club: c.clubName,
            league: leagueLabel(
              vm.candidate(c.playerId).value?.season?.leagueId,
            ),
          ),
      ],
      slot: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        spacing: 8,
        children: [
          Text(
            '${formatNumber(candidates.length)} de 3 reemplazos',
            style: DelphosText.ui(
              size: TypeScale.secondary,
              weight: FontWeight.w500,
              color: DelphosColors.ink3,
            ),
          ),
          Text(
            slotText,
            style: DelphosText.ui(color: DelphosColors.ink2, height: 1.5),
          ),
        ],
      ),
    );
    return Semantics(
      container: true,
      label: 'Comparación de ${reference.name} con sus reemplazos',
      child: Container(
        clipBehavior: Clip.antiAlias,
        decoration: BoxDecoration(
          color: DelphosColors.surface,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: DelphosColors.rule),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            header,
            ...compareTableBody(
              vm: vm,
              candidates: candidates,
              missingSlots: missing,
              datasetSeason: datasetSeason,
            ),
          ],
        ),
      ),
    );
  }
}
