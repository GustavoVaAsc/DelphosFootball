/// A column header of the comparison table (DESIGN.md §4): the kicker
/// ("Referencia", "Reemplazo 1"), then the 40 px portrait with its 17 px
/// crest, the name with its flag, and the club. The league is not here: the
/// "Liga" row of the table states it.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/flag_image.dart';
import '../../../core/widgets/player_avatar.dart';

/// One player's column header.
class ComparePlayerHead extends StatelessWidget {
  const ComparePlayerHead({
    super.key,
    required this.kicker,
    required this.name,
    this.isReference = false,
    this.imageUrl,
    this.crestUrl,
    this.country,
    this.club,
  });

  final String kicker;
  final String name;

  /// The reference's kicker is ink and semi-bold; candidates' are muted.
  final bool isReference;
  final String? imageUrl;
  final String? crestUrl;
  final String? country;
  final String? club;

  @override
  Widget build(BuildContext context) {
    final sub = DelphosText.ui(
      size: TypeScale.secondary,
      color: DelphosColors.ink2,
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: 8,
      children: [
        Text(
          kicker,
          style: DelphosText.ui(
            size: TypeScale.secondary,
            weight: isReference ? FontWeight.w600 : FontWeight.w500,
            color: isReference ? DelphosColors.ink : DelphosColors.ink3,
          ),
        ),
        Row(
          spacing: 10,
          children: [
            PlayerAvatar(
              imageUrl: imageUrl,
              crestUrl: crestUrl,
              size: 40,
              crestSize: 17,
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                spacing: 2,
                children: [
                  Row(
                    spacing: 4,
                    children: [
                      Flexible(
                        child: Text(
                          name,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: DelphosText.condensed(height: 1.2),
                        ),
                      ),
                      FlagImage(country: country),
                    ],
                  ),
                  if (club != null) Text(club!, style: sub),
                ],
              ),
            ),
          ],
        ),
      ],
    );
  }
}
