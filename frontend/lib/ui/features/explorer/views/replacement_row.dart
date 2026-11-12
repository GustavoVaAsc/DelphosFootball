/// One replacement candidate in the dossier (DESIGN.md §4, Replacements):
/// 40 px portrait with a 17 px crest, the name with its flag, the club
/// (truncated, full name in a tooltip) with "· NN% de similitud" kept on
/// one line, and on the right the price and the saving in ink.
library;

import 'package:material_ui/material_ui.dart';

import '../../../../domain/models/replacement.dart';
import '../../../core/format/money.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/flag_image.dart';
import '../../../core/widgets/player_avatar.dart';
import 'dossier_text.dart';

/// A candidate row.
class ReplacementRow extends StatelessWidget {
  const ReplacementRow({super.key, required this.candidate});

  final Replacement candidate;

  @override
  Widget build(BuildContext context) {
    final c = candidate;
    final small = DelphosText.ui(
      size: TypeScale.secondary,
      color: DelphosColors.ink2,
      tabular: true,
    );
    return Row(
      spacing: 10,
      children: [
        PlayerAvatar(
          imageUrl: c.imageUrl,
          crestUrl: c.clubLogoUrl,
          size: 40,
          crestSize: 17,
        ),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            spacing: 1,
            children: [
              Row(
                spacing: 6,
                children: [
                  Flexible(
                    child: Text(
                      c.name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: DelphosText.condensed(),
                    ),
                  ),
                  FlagImage(country: c.country),
                ],
              ),
              Row(
                spacing: 4,
                children: [
                  if (c.clubName case final club?)
                    Flexible(
                      child: Tooltip(
                        message: club,
                        excludeFromSemantics: true,
                        child: Text(
                          club,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: small,
                        ),
                      ),
                    ),
                  Text(
                    similarityText(c),
                    maxLines: 1,
                    softWrap: false,
                    style: small,
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
            Text(formatEur(c.marketValueEur), style: DelphosText.condensed()),
            Text(
              replacementSavings(c),
              maxLines: 1,
              softWrap: false,
              style: small,
            ),
          ],
        ),
      ],
    );
  }
}
