/// An archetype card's representative players (DESIGN.md §4): a compact
/// list of buttons, flag and name on the left, price on the right,
/// hairlines between rows. Each opens the player's dossier in the explorer.
library;

import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

import '../../../../domain/models/player_summary.dart';
import '../../../../routing/explorer_query.dart';
import '../../../core/format/money.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/view_models/section_load.dart';
import '../../../core/view_models/section_status.dart';
import '../../../core/widgets/flag_image.dart';
import '../../../core/widgets/pressable.dart';

/// "Jugadores representativos" and their rows, for one load state.
class RepresentativeList extends StatelessWidget {
  const RepresentativeList({super.key, required this.load});

  final SectionLoad<List<PlayerSummary>> load;

  @override
  Widget build(BuildContext context) {
    final muted = DelphosText.ui(color: DelphosColors.ink2);
    final players = load.value ?? const <PlayerSummary>[];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Text(
            'Jugadores representativos',
            style: DelphosText.ui(
              size: TypeScale.secondary,
              weight: FontWeight.w500,
              color: DelphosColors.ink3,
            ),
          ),
        ),
        if (load.status == SectionStatus.loading)
          Text('Cargando jugadores…', style: muted)
        else if (load.status != SectionStatus.ready)
          Text(
            'No se pudieron cargar los jugadores representativos.',
            style: muted,
          )
        else
          for (var i = 0; i < players.length; i++)
            DecoratedBox(
              decoration: BoxDecoration(
                border: i == 0
                    ? null
                    : const Border(top: BorderSide(color: DelphosColors.rule)),
              ),
              child: _Row(player: players[i]),
            ),
      ],
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.player});

  final PlayerSummary player;

  @override
  Widget build(BuildContext context) {
    final price = formatEur(player.marketValueEur);
    return Pressable(
      onPressed: () =>
          context.go(ExplorerQuery(playerId: player.id).toLocation()),
      semanticLabel: '${player.name}, $price',
      borderRadius: 2,
      pressedScale: 1,
      builder: (context, hovered) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(
          spacing: 8,
          children: [
            FlagImage(country: player.country),
            Expanded(
              child: Text(
                player.name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: DelphosText.ui().copyWith(
                  decoration: hovered ? TextDecoration.underline : null,
                  decorationColor: DelphosColors.ink,
                ),
              ),
            ),
            Text(
              price,
              style: DelphosText.ui(color: DelphosColors.ink2, tabular: true),
            ),
          ],
        ),
      ),
    );
  }
}
