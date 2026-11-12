/// The comparison table while the reference loads (DESIGN.md §7): the
/// table's frame with static blocks in place of the headers and values. No
/// shimmer, no pulse.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import 'compare_row.dart';

/// A static stand-in for the comparison table.
class CompareSkeleton extends StatelessWidget {
  const CompareSkeleton({super.key});

  static Widget _block(double width, double height, {double radius = 4}) =>
      Container(
        width: width,
        height: height,
        decoration: BoxDecoration(
          color: DelphosColors.surfaceMuted,
          borderRadius: BorderRadius.circular(radius),
        ),
      );

  @override
  Widget build(BuildContext context) {
    Widget head() => Row(
      spacing: 10,
      children: [
        _block(40, 40, radius: 20),
        Flexible(child: _block(120, 12)),
      ],
    );
    return ExcludeSemantics(
      child: Container(
        clipBehavior: Clip.antiAlias,
        decoration: BoxDecoration(
          color: DelphosColors.surface,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: DelphosColors.rule),
        ),
        child: Column(
          children: [
            CompareRow(
              verticalPadding: 14,
              referenceGround: DelphosColors.surfaceMuted,
              metric: const SizedBox.shrink(),
              reference: head(),
              candidates: [head(), head(), head()],
            ),
            for (var i = 0; i < 6; i++)
              CompareRow(
                metric: _block(110, 10),
                reference: _block(70, 10),
                candidates: [_block(70, 10), _block(70, 10), _block(70, 10)],
                last: i == 5,
              ),
          ],
        ),
      ),
    );
  }
}
