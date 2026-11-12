/// A column header of the comparison table (DESIGN.md §4): the kicker
/// ("Referencia · Activo élite", "Reemplazo 1"), then the 40 px portrait
/// with its 17 px crest, the name with its flag, the club on one line and
/// the league on the next, with no separator.
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
    this.eliteAsset = false,
    this.imageUrl,
    this.crestUrl,
    this.country,
    this.club,
    this.league,
  });

  final String kicker;
  final String name;

  /// The reference's kicker is ink and semi-bold; candidates' are muted.
  final bool isReference;
  final bool eliteAsset;
  final String? imageUrl;
  final String? crestUrl;
  final String? country;
  final String? club;
  final String? league;

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
        Text.rich(
          TextSpan(
            text: kicker,
            style: DelphosText.ui(
              size: TypeScale.secondary,
              weight: isReference ? FontWeight.w600 : FontWeight.w500,
              color: isReference ? DelphosColors.ink : DelphosColors.ink3,
            ),
            children: [
              if (eliteAsset)
                TextSpan(
                  text: ' · Activo élite',
                  style: DelphosText.ui(
                    size: TypeScale.secondary,
                    weight: FontWeight.w500,
                    color: DelphosColors.ink2,
                  ),
                ),
            ],
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
                  if (league != null)
                    Text(league!, maxLines: 1, softWrap: false, style: sub),
                ],
              ),
            ),
          ],
        ),
      ],
    );
  }
}
