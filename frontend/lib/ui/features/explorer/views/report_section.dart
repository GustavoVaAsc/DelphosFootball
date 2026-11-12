/// The dossier's Resumen content (DESIGN.md §4 and §7): the stored or new
/// scouting report with its provenance and "Regenerar"; "Generar informe"
/// when there is none; while generating, one static line with the elapsed
/// seconds and "Cancelar"; one sentence and "Reintentar" on a failure. The
/// rest of the dossier stays usable throughout.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/action_button.dart';
import '../../../core/widgets/fade_in_once.dart';
import '../view_models/report_status.dart';
import '../view_models/report_view_model.dart';
import 'dossier_load_error.dart';
import 'report_prose.dart';
import 'report_text.dart';
import 'section_skeleton.dart';

/// The Resumen for the player [vm] is on.
class ReportSection extends StatelessWidget {
  const ReportSection({super.key, required this.vm});

  final ReportViewModel vm;

  /// A sentence and its action. With [announce], screen readers hear that
  /// label once instead of the sentence, whose seconds change every second.
  static Widget _line(String text, Widget action, {String? announce}) {
    final sentence = Text(
      text,
      style: DelphosText.ui(color: DelphosColors.ink2, tabular: true),
    );
    return Row(
      spacing: 12,
      children: [
        Flexible(
          child: announce == null
              ? sentence
              : Semantics(
                  liveRegion: true,
                  label: announce,
                  child: ExcludeSemantics(child: sentence),
                ),
        ),
        action,
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: vm,
      builder: (context, _) => switch (vm.status) {
        ReportStatus.idle => const SizedBox.shrink(),
        ReportStatus.checking => const SectionSkeleton(),
        ReportStatus.none => _line(
          'Este jugador todavía no tiene informe de scouting.',
          ActionButton(label: 'Generar informe', onPressed: vm.generate),
        ),
        ReportStatus.generating => _line(
          generatingLine(vm.elapsedSeconds),
          ActionButton(label: 'Cancelar', onPressed: vm.cancel),
          announce: 'Generando el informe',
        ),
        ReportStatus.error => DossierLoadError(
          message: vm.generationFailed
              ? 'No se pudo generar el informe.'
              : 'No se pudo cargar el informe.',
          onRetry: vm.retry,
        ),
        ReportStatus.ready => Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          spacing: 10,
          children: [
            // The report fades in once when it arrives (160 ms opacity,
            // instant under reduced motion); a new report fades in again.
            FadeInOnce(
              key: ValueKey(vm.report!.id),
              child: ReportProse(html: vm.report!.html),
            ),
            Text(
              reportProvenance(vm.report!),
              style: DelphosText.ui(
                size: TypeScale.secondary,
                color: DelphosColors.ink3,
              ),
            ),
            ActionButton(label: 'Regenerar', onPressed: vm.regenerate),
          ],
        ),
      },
    );
  }
}
