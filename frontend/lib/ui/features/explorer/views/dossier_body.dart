/// The scrolling body of the dossier (DESIGN.md §4): Valoración, Temporada,
/// Reemplazos and Resumen (the scouting report). Each section follows its
/// own request, so one failure shows one retry line and the rest of the
/// dossier stays readable.
library;

import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

import '../../../../routing/routes.dart';
import '../../../core/format/dates.dart';
import '../../../core/labels/archetypes.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/widgets/action_button.dart';
import '../../../core/widgets/fade_in_once.dart';
import '../view_models/dossier_view_model.dart';
import '../../../core/view_models/section_load.dart';
import '../../../core/view_models/section_status.dart';
import 'dossier_load_error.dart';
import 'dossier_section.dart';
import 'section_skeleton.dart';
import 'replacements_list.dart';
import 'report_section.dart';
import 'season_section.dart';
import 'valuation_section.dart';

/// The dossier sections for the player on show.
class DossierBody extends StatelessWidget {
  const DossierBody({super.key, required this.vm, this.datasetSeason});

  final DossierViewModel vm;

  /// The season to title the grid with when the player has no season row.
  final int? datasetSeason;

  @override
  Widget build(BuildContext context) {
    final profile = vm.profile;
    final playerId = vm.playerId;
    final season = profile?.season;
    final seasonYear = season?.season ?? datasetSeason;
    final archetype = archetypeShortName(profile?.clusterId);
    final seasonNotes = [
      ?archetype,
      if (season != null) 'datos al ${formatDate(season.asOfDate)}',
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        DossierSection(
          title: null,
          first: true,
          child: _content(
            vm.valuation,
            (valuation) => ValuationSection(valuation: valuation),
            absent: 'Sin valoración del modelo para este jugador.',
            error: 'No se pudo cargar la valoración.',
          ),
        ),
        DossierSection(
          title: seasonYear == null
              ? 'Temporada'
              : 'Temporada ${formatSeason(seasonYear)}',
          subtitle: seasonNotes.isEmpty ? null : seasonNotes.join(' · '),
          child: _content(
            vm.identity,
            (profile) => SeasonSection(season: profile.season),
            error: 'No se pudo cargar la temporada.',
          ),
        ),
        DossierSection(
          title: 'Reemplazos',
          subtitle: 'Mismo arquetipo y posición · ahorro ≥\u00A020%',
          action: playerId == null
              ? null
              : ActionButton(
                  label: 'Comparar reemplazos',
                  onPressed: () => context.go(Routes.comparatorFor(playerId)),
                ),
          child: _content(
            vm.replacements,
            (set) => ReplacementsList(set: set),
            absent: 'Este jugador no tiene reemplazos calculados.',
            error: 'No se pudieron cargar los reemplazos.',
          ),
        ),
        DossierSection(
          title: 'Resumen',
          child: ReportSection(vm: vm.report),
        ),
      ],
    );
  }

  /// A section's content for its load state. Data fades in once when it
  /// arrives (keyed by player, so a new player fades in again).
  Widget _content<T>(
    SectionLoad<T> load,
    Widget Function(T value) ready, {
    required String error,
    String absent = '',
  }) {
    return switch (load.status) {
      SectionStatus.loading => const SectionSkeleton(),
      SectionStatus.ready => FadeInOnce(
        key: ValueKey(vm.playerId),
        child: ready(load.value as T),
      ),
      SectionStatus.absent => Text(
        absent,
        style: DelphosText.ui(color: DelphosColors.ink2),
      ),
      SectionStatus.error => DossierLoadError(
        message: error,
        onRetry: vm.retry,
      ),
    };
  }
}
