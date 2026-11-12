/// The dossier's identity header (DESIGN.md §4, Dossier): 64 px portrait
/// with a 24 px crest, the name at 20/700 condensed with "Activo élite" as
/// plain secondary text when it applies, the country, club and league line,
/// then the Edad · Altura · Pie · Posición row.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/player_profile.dart';
import '../../../core/format/format.dart';
import '../../../core/labels/feet.dart';
import '../../../core/labels/positions.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/player_avatar.dart';
import 'bio_row.dart';
import 'dossier_club_line.dart';

/// The identity block of one player.
class DossierHeader extends StatelessWidget {
  const DossierHeader({
    super.key,
    required this.profile,
    this.eliteAsset = false,
    this.dataDate,
  });

  final PlayerProfile profile;

  /// From the replacements; shown as plain text, never a pill or a colour.
  final bool eliteAsset;

  /// The latest data date, for the age of a player without a season row.
  final DateTime? dataDate;

  /// Whole years: the season age, else the age at the latest data date.
  int? get _age =>
      profile.season?.age.floor() ?? ageOn(profile.dateOfBirth, dataDate);

  @override
  Widget build(BuildContext context) {
    final age = _age;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      spacing: 12,
      children: [
        Row(
          spacing: 14,
          children: [
            PlayerAvatar.large(
              imageUrl: profile.imageUrl,
              crestUrl: profile.clubLogoUrl,
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                spacing: 4,
                children: [
                  // Room on the right for the close button, on this line only.
                  Padding(
                    padding: const EdgeInsets.only(right: 32),
                    child: Row(
                      spacing: 10,
                      crossAxisAlignment: CrossAxisAlignment.baseline,
                      textBaseline: TextBaseline.alphabetic,
                      children: [
                        Flexible(
                          child: Semantics(
                            header: true,
                            child: Text(
                              profile.name,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: DelphosText.condensed(
                                size: TypeScale.title,
                                height: 1.2,
                              ),
                            ),
                          ),
                        ),
                        if (eliteAsset)
                          Text(
                            'Activo élite',
                            maxLines: 1,
                            softWrap: false,
                            style: DelphosText.ui(
                              size: TypeScale.secondary,
                              weight: FontWeight.w500,
                              color: DelphosColors.ink2,
                            ),
                          ),
                      ],
                    ),
                  ),
                  DossierClubLine(profile: profile),
                ],
              ),
            ),
          ],
        ),
        BioRow(
          items: [
            ('Edad', age == null ? notAvailable : formatNumber(age)),
            ('Altura', formatHeight(profile.heightCm)),
            ('Pie', footLabel(profile.foot) ?? notAvailable),
            (
              'Posición',
              roleLabel(
                    position: profile.position,
                    subPosition: profile.subPosition,
                  ) ??
                  notAvailable,
            ),
          ],
        ),
      ],
    );
  }
}
