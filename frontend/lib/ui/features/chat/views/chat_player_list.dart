/// Clickable player rows hydrated outside the LLM and shown below PitIA's
/// answer inside the assistant bubble (DESIGN.md §4 PitIA).
library;

import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

import '../../../../domain/models/chat_referenced_player.dart';
import '../../../../routing/explorer_query.dart';
import '../../../core/format/money.dart';
import '../../../core/labels/league_logos.dart';
import '../../../core/labels/positions.dart';
import '../../../core/labels/valuation_labels.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_radius.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/flag_image.dart';
import '../../../core/widgets/player_avatar.dart';
import '../../../core/widgets/pressable.dart';
import '../../../core/widgets/remote_logo.dart';
import '../../../core/widgets/status_text.dart';

/// Compact list of players mentioned in PitIA's reply; each row opens the
/// player's dossier in the explorer.
class ChatPlayerList extends StatelessWidget {
  const ChatPlayerList({super.key, required this.players});

  final List<ChatReferencedPlayer> players;

  @override
  Widget build(BuildContext context) {
    if (players.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      spacing: 4,
      children: [
        Text(
          'Jugadores mencionados',
          style: DelphosText.ui(
            size: TypeScale.secondary,
            weight: FontWeight.w600,
            color: DelphosColors.ink3,
          ),
        ),
        for (final (i, player) in players.indexed)
          DecoratedBox(
            decoration: BoxDecoration(
              border: i == 0
                  ? null
                  : const Border(top: BorderSide(color: DelphosColors.rule)),
            ),
            child: _ChatPlayerRow(player: player),
          ),
      ],
    );
  }
}

class _ChatPlayerRow extends StatelessWidget {
  const _ChatPlayerRow({required this.player});

  final ChatReferencedPlayer player;

  @override
  Widget build(BuildContext context) {
    final price = formatEur(player.marketValueEur);
    final role = roleLabel(
      position: player.position,
      subPosition: player.subPosition,
    );
    final subtitle = [?player.clubName, ?role].join(' · ');
    final semantic = [
      player.name,
      ?player.clubName,
      price,
      if (player.valuationStatus case final status?)
        valuationStatusLabel(status),
    ].join(', ');

    return Pressable(
      onPressed: () =>
          context.go(ExplorerQuery(playerId: player.id).toLocation()),
      semanticLabel: semantic,
      borderRadius: DelphosRadius.control,
      pressedScale: 1,
      builder: (context, hovered) => DecoratedBox(
        decoration: BoxDecoration(
          color: hovered ? DelphosColors.surfaceSubtle : null,
          borderRadius: BorderRadius.circular(DelphosRadius.control),
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 8),
          child: Row(
            spacing: 10,
            children: [
              PlayerAvatar(
                imageUrl: player.imageUrl,
                crestUrl: player.clubLogoUrl,
                size: 38,
                crestSize: 16,
              ),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  spacing: 2,
                  children: [
                    Row(
                      spacing: 6,
                      children: [
                        Flexible(
                          child: Text(
                            player.name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: DelphosText.condensed().copyWith(
                              decoration: hovered
                                  ? TextDecoration.underline
                                  : null,
                              decorationColor: DelphosColors.ink,
                            ),
                          ),
                        ),
                        FlagImage(country: player.country),
                      ],
                    ),
                    Row(
                      spacing: 5,
                      children: [
                        RemoteLogo(
                          url: leagueLogoUrl(player.leagueId),
                          height: 14,
                        ),
                        if (subtitle.isNotEmpty)
                          Flexible(
                            child: Text(
                              subtitle,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: DelphosText.ui(
                                size: TypeScale.secondary,
                                color: DelphosColors.ink2,
                              ),
                            ),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                spacing: 2,
                children: [
                  Text(price, style: DelphosText.condensed()),
                  if (player.valuationStatus case final status?)
                    StatusText(status: status),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
