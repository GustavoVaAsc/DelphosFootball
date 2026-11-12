/// One line of the comparison table (DESIGN.md §4, Comparador Moneyball):
/// the 200 px metric column, the reference column (set apart by its ground,
/// no colour stripe), one column per candidate, and, with fewer than three
/// candidates, the placeholder column spanning the missing slots. All cells
/// of a line share its height, so grounds and hairlines line up.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';

/// Lays out the cells of one table line.
class CompareRow extends StatelessWidget {
  const CompareRow({
    super.key,
    required this.metric,
    required this.reference,
    required this.candidates,
    this.missingSlots = 0,
    this.slot,
    this.referenceGround = DelphosColors.surfaceSubtle,
    this.verticalPadding = 10,
    this.last = false,
  });

  final Widget metric;
  final Widget reference;
  final List<Widget> candidates;

  /// How many of the three candidate slots are empty.
  final int missingSlots;

  /// The placeholder column's content (only the header line has one).
  final Widget? slot;

  /// Muted for the header line, subtle for the body.
  final Color referenceGround;
  final double verticalPadding;

  /// The last line has no hairline below it.
  final bool last;

  static const double metricWidth = 200;

  @override
  Widget build(BuildContext context) {
    Widget cell(Widget child, {Color? ground}) => Container(
      color: ground,
      padding: EdgeInsets.symmetric(horizontal: 14, vertical: verticalPadding),
      alignment: Alignment.centerLeft,
      child: child,
    );
    return Container(
      decoration: BoxDecoration(
        border: last
            ? null
            : const Border(bottom: BorderSide(color: DelphosColors.rule)),
      ),
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SizedBox(width: metricWidth, child: cell(metric)),
            Expanded(child: cell(reference, ground: referenceGround)),
            for (final candidate in candidates)
              Expanded(child: cell(candidate)),
            if (missingSlots > 0)
              Expanded(
                flex: missingSlots,
                child: cell(
                  slot ?? const SizedBox.shrink(),
                  ground: DelphosColors.surfaceSubtle,
                ),
              ),
          ],
        ),
      ),
    );
  }
}
