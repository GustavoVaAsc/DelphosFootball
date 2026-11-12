/// The Comparador Moneyball (DESIGN.md §4 and §7): the player selector and
/// the way back to the explorer, then the comparison table. Without a
/// player it shows one plain line, never a fake table; while the reference
/// loads, a static skeleton; when it cannot load, one panel with
/// "Reintentar".
library;

import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../../../../data/repositories/player_repository.dart';
import '../../../../routing/explorer_query.dart';
import '../../../../routing/routes.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/view_models/dataset_view_model.dart';
import '../../../core/widgets/action_button.dart';
import '../view_models/comparator_status.dart';
import '../view_models/comparator_view_model.dart';
import '../view_models/player_search_view_model.dart';
import 'compare_skeleton.dart';
import 'compare_table.dart';
import 'comparator_error_panel.dart';
import 'player_selector.dart';

/// The comparator for the reference player [playerId], or the empty page.
class ComparatorScreen extends StatefulWidget {
  const ComparatorScreen({super.key, this.playerId});

  final int? playerId;

  @override
  State<ComparatorScreen> createState() => _ComparatorScreenState();
}

class _ComparatorScreenState extends State<ComparatorScreen> {
  late final ComparatorViewModel _vm = ComparatorViewModel(
    players: context.read<PlayerRepository>(),
  )..show(widget.playerId);
  late final PlayerSearchViewModel _search = PlayerSearchViewModel(
    players: context.read<PlayerRepository>(),
  );

  @override
  void didUpdateWidget(ComparatorScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    _vm.show(widget.playerId);
  }

  @override
  void dispose() {
    _vm.dispose();
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final dataset = context.watch<DatasetViewModel?>();
    final id = widget.playerId;
    final toolbar = Container(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      decoration: BoxDecoration(
        color: DelphosColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: DelphosColors.rule),
      ),
      child: Row(
        spacing: 12,
        children: [
          Text(
            'Jugador analizado',
            style: DelphosText.ui(
              size: TypeScale.secondary,
              weight: FontWeight.w500,
              color: DelphosColors.ink3,
            ),
          ),
          PlayerSelector(
            vm: _search,
            onPick: (playerId) => context.go(Routes.comparatorFor(playerId)),
          ),
          const Spacer(),
          if (id != null)
            ActionButton(
              label: 'Volver al Explorador de Mercado',
              onPressed: () =>
                  context.go(ExplorerQuery(playerId: id).toLocation()),
            ),
        ],
      ),
    );
    return ListenableBuilder(
      listenable: _vm,
      builder: (context, _) {
        final Widget content = switch (_vm.status) {
          ComparatorStatus.idle => Text(
            'Elige un jugador para comparar con sus reemplazos.',
            style: DelphosText.ui(color: DelphosColors.ink2),
          ),
          ComparatorStatus.loading => const CompareSkeleton(),
          ComparatorStatus.error => ComparatorErrorPanel(onRetry: _vm.retry),
          ComparatorStatus.ready => CompareTable(
            vm: _vm,
            datasetSeason: dataset?.overview?.season,
          ),
        };
        return SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 20, 24, 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            spacing: 18,
            children: [toolbar, content],
          ),
        );
      },
    );
  }
}
