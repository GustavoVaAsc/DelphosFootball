/// Line 2 of the dossier header (DESIGN.md §4): flag and country, the club
/// crest and club name, the league logo and league name, separated by " · ".
/// It never wraps. Names that fit are never cut. When the line is too wide,
/// the club name is cut first, with an ellipsis, and only then the country;
/// the flag, the 28 px logos, the league name and the dots never shrink
/// (`ShrinkRow` decides this in layout, from the real widths). The full
/// country and club stay in the semantics label. A logo that is missing or
/// fails to load shows nothing and takes no width, and a player with no
/// season row has no league, so that item and its dot are omitted.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/player_profile.dart';
import '../../../core/labels/countries.dart';
import '../../../core/labels/league_logos.dart';
import '../../../core/labels/leagues.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/widgets/flag_image.dart';
import '../../../core/widgets/remote_logo.dart';
import '../../../core/widgets/shrink_row.dart';

/// Country, club and league of one player.
class DossierIdentityLine extends StatelessWidget {
  const DossierIdentityLine({super.key, required this.profile});

  final PlayerProfile profile;

  /// Crest and league logo height, set apart from the 13 px text.
  static const double logo = 28;

  @override
  Widget build(BuildContext context) {
    final country = countryNameEs(profile.country);
    final club = profile.clubName;
    final leagueId = profile.season?.leagueId;
    final league = leagueLabel(leagueId);
    final plain = DelphosText.ui(color: DelphosColors.ink2);
    final bold = DelphosText.ui(
      color: DelphosColors.ink,
      weight: FontWeight.w600,
    );
    Widget text(String value, TextStyle style) => Text(
      value,
      maxLines: 1,
      softWrap: false,
      overflow: TextOverflow.ellipsis,
      style: style,
    );
    // A logo has its own 6 px gap after it only while it shows, so a missing
    // one leaves exactly one gap between the dot and the name.
    Widget logoOf(String? url) =>
        RemoteLogo(url: url, height: logo, gapAfter: 6);

    final children = <Widget>[];
    void dot() {
      if (children.isNotEmpty) {
        children.add(ShrinkItem(child: Text('·', style: plain)));
      }
    }

    if (country != null) {
      children
        ..add(
          ShrinkItem(gapBefore: 0, child: FlagImage(country: profile.country)),
        )
        ..add(ShrinkItem(shrink: 2, child: text(country, plain)));
    }
    if (club != null) {
      dot();
      children
        ..add(ShrinkItem(child: logoOf(profile.clubLogoUrl)))
        ..add(ShrinkItem(gapBefore: 0, shrink: 1, child: text(club, bold)));
    }
    if (league != null) {
      dot();
      children
        ..add(ShrinkItem(child: logoOf(leagueLogoUrl(leagueId))))
        ..add(ShrinkItem(gapBefore: 0, child: text(league, plain)));
    }
    return Semantics(
      container: true,
      label: [?country, ?club, ?league].join(' · '),
      excludeSemantics: true,
      child: ShrinkRow(children: children),
    );
  }
}
