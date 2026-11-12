/// One legend entry under the archetype share bar (DESIGN.md §4): a small
/// swatch in the segment's tone, the archetype name, and under it the count
/// and share, "1.219 · 22%".
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';

/// The legend entry for one share bar segment.
class ShareLegendItem extends StatelessWidget {
  const ShareLegendItem({
    super.key,
    required this.name,
    required this.count,
    required this.tone,
  });

  final String name;
  final String count;
  final Color tone;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: 1,
      children: [
        Row(
          spacing: 6,
          children: [
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                color: tone,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            Flexible(
              child: Text(
                name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: DelphosText.ui(weight: FontWeight.w600),
              ),
            ),
          ],
        ),
        Padding(
          padding: const EdgeInsets.only(left: 14),
          child: Text(
            count,
            maxLines: 1,
            softWrap: false,
            style: DelphosText.ui(
              size: TypeScale.secondary,
              color: DelphosColors.ink2,
              tabular: true,
            ),
          ),
        ),
      ],
    );
  }
}
