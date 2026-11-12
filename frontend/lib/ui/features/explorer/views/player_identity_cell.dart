/// The Jugador cell of a table row (DESIGN.md §4): portrait with crest, then
/// three lines: the name (the row's real control), flag and club, and the
/// archetype as muted text.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/player_summary.dart';
import '../../../core/labels/archetypes.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/flag_image.dart';
import '../../../core/widgets/player_avatar.dart';
import '../../../core/widgets/pressable.dart';

/// The identity cell; the name opens and closes the player's dossier.
class PlayerIdentityCell extends StatelessWidget {
  const PlayerIdentityCell({
    super.key,
    required this.player,
    required this.dossierOpen,
    required this.onToggle,
    required this.nameFocusNode,
  });

  final PlayerSummary player;

  /// Whether this player's dossier is open (`aria-expanded`).
  final bool dossierOpen;
  final VoidCallback onToggle;
  final FocusNode nameFocusNode;

  @override
  Widget build(BuildContext context) {
    final archetype = archetypeShortName(player.clusterId);
    final secondary = DelphosText.ui(
      size: TypeScale.secondary,
      color: DelphosColors.ink2,
      height: 1.3,
    );
    return Row(
      spacing: 12,
      children: [
        PlayerAvatar(imageUrl: player.imageUrl, crestUrl: player.clubLogoUrl),
        Expanded(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Pressable(
                onPressed: onToggle,
                semanticLabel: player.name,
                expanded: dossierOpen,
                focusNode: nameFocusNode,
                borderRadius: 2,
                pressedScale: 1,
                builder: (_, _) => Text(
                  player.name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: DelphosText.condensed(height: 1.25),
                ),
              ),
              const SizedBox(height: 2),
              Row(
                spacing: 5,
                children: [
                  FlagImage(country: player.country),
                  Flexible(
                    child: Text(
                      player.clubName ?? '',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: secondary,
                    ),
                  ),
                ],
              ),
              if (archetype != null)
                Text(
                  archetype,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: secondary.copyWith(color: DelphosColors.ink3),
                ),
            ],
          ),
        ),
      ],
    );
  }
}
