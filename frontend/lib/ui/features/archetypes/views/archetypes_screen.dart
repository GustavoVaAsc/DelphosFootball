/// The Arquetipos Tácticos view (DESIGN.md §4): the intro card with the
/// share bar, then the three archetype cards. Loading is one plain line
/// ("Cargando datos…", DESIGN.md §7), and an unreachable server is one
/// panel with "Reintentar".
library;

import 'package:flutter/widgets.dart';
import 'package:provider/provider.dart';

import '../../../../data/repositories/archetype_repository.dart';
import '../../../../data/repositories/player_repository.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/view_models/section_status.dart';
import '../../../core/widgets/action_button.dart';
import '../../../core/widgets/state_panel.dart';
import '../view_models/archetypes_view_model.dart';
import 'archetype_grid.dart';
import 'archetype_intro.dart';

/// The archetype explorer.
class ArchetypesScreen extends StatefulWidget {
  const ArchetypesScreen({super.key});

  @override
  State<ArchetypesScreen> createState() => _ArchetypesScreenState();
}

class _ArchetypesScreenState extends State<ArchetypesScreen> {
  late final ArchetypesViewModel _vm = ArchetypesViewModel(
    archetypes: context.read<ArchetypeRepository>(),
    players: context.read<PlayerRepository>(),
  )..load();

  @override
  void dispose() {
    _vm.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: _vm,
      builder: (context, _) {
        final overview = _vm.overview;
        final Widget content = switch (overview.status) {
          SectionStatus.ready => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            spacing: 18,
            children: [
              ArchetypeIntro(overview: overview.value!),
              ArchetypeGrid(
                archetypes: overview.value!.archetypes,
                representatives: _vm.representatives,
              ),
            ],
          ),
          SectionStatus.loading => Text(
            'Cargando datos…',
            style: DelphosText.ui(color: DelphosColors.ink2),
          ),
          _ => DecoratedBox(
            decoration: BoxDecoration(
              color: DelphosColors.surface,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: DelphosColors.rule),
            ),
            child: StatePanel(
              title: 'No se pudo conectar con el servidor de datos',
              text:
                  'Los datos del mercado no están disponibles ahora mismo. '
                  'Comprueba la conexión e inténtalo de nuevo.',
              action: ActionButton(
                label: 'Reintentar',
                primary: true,
                onPressed: _vm.load,
              ),
            ),
          ),
        };
        return SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 20, 24, 32),
          child: content,
        );
      },
    );
  }
}
