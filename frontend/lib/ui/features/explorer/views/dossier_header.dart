/// The dossier's identity header (DESIGN.md §4, Dossier): the 64 px portrait
/// beside three lines: the name at 20/700 condensed (with room for the close
/// button); flag, country, crest and club, league logo and league on one
/// line; and the Edad | Altura | Pie | Posición row with hairlines.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/player_profile.dart';
import '../../../core/format/format.dart';
import '../../../core/labels/feet.dart';
import '../../../core/labels/positions.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/player_avatar.dart';
import 'dossier_definition_row.dart';
import 'dossier_identity_line.dart';

/// The identity block of one player.
class DossierHeader extends StatelessWidget {
  const DossierHeader({super.key, required this.profile, this.dataDate});

  final PlayerProfile profile;

  /// The latest data date, for the age of a player without a season row.
  final DateTime? dataDate;

  /// Whole years: the season age, else the age at the latest data date.
  int? get _age =>
      profile.season?.age.floor() ?? ageOn(profile.dateOfBirth, dataDate);

  @override
  Widget build(BuildContext context) {
    final age = _age;
    final height = formatHeight(profile.heightCm);
    final foot = footLabel(profile.foot);
    final role = roleLabel(
      position: profile.position,
      subPosition: profile.subPosition,
    );
    final definition = <(String, String)>[
      if (age != null) ('Edad', formatNumber(age)),
      if (height != notAvailable) ('Altura', height),
      if (foot != null) ('Pie', foot),
      if (role != null) ('Posición', role),
    ];
    return Row(
      spacing: 14,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // The portrait alone, with no crest disc: the logos are on line 2.
        PlayerAvatar.large(imageUrl: profile.imageUrl),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            spacing: 4,
            children: [
              // Room on the right for the close button, on this line only.
              Padding(
                padding: const EdgeInsets.only(right: 32),
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
              DossierIdentityLine(profile: profile),
              // An item the data lacks is left out, never printed as "N/D";
              // with none, the row and its spacing are not built.
              if (definition.isNotEmpty) ...[
                const SizedBox(height: 4),
                DossierDefinitionRow(items: definition),
              ],
            ],
          ),
        ),
      ],
    );
  }
}
