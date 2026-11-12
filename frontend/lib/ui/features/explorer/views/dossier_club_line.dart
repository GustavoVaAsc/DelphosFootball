/// The dossier's identity line: flag and country, club, league. It wraps
/// between items, never inside one, and each "·" ends the item before it,
/// so no line starts with one (DESIGN.md §4).
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/player_profile.dart';
import '../../../core/labels/countries.dart';
import '../../../core/labels/leagues.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/widgets/flag_image.dart';

/// Country, club and league of one player.
class DossierClubLine extends StatelessWidget {
  const DossierClubLine({super.key, required this.profile});

  final PlayerProfile profile;

  @override
  Widget build(BuildContext context) {
    final country = countryNameEs(profile.country);
    final league = leagueLabel(profile.season?.leagueId);
    final base = DelphosText.ui(color: DelphosColors.ink2);
    final items = <Widget>[
      if (country != null)
        Row(
          mainAxisSize: MainAxisSize.min,
          spacing: 6,
          children: [
            FlagImage(country: profile.country),
            Text(country, style: base),
          ],
        ),
      if (profile.clubName case final club?)
        Text(
          club,
          style: DelphosText.ui(
            color: DelphosColors.ink,
            weight: FontWeight.w600,
          ),
        ),
      if (league != null) Text(league, style: base),
    ];
    return Wrap(
      spacing: 6,
      runSpacing: 2,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        for (var i = 0; i < items.length; i++)
          i == items.length - 1
              ? items[i]
              : Row(
                  mainAxisSize: MainAxisSize.min,
                  spacing: 6,
                  children: [
                    items[i],
                    ExcludeSemantics(child: Text('·', style: base)),
                  ],
                ),
      ],
    );
  }
}
