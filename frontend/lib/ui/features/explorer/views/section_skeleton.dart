/// The placeholder of a dossier section while its request runs.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';

/// Two static bars while a section loads (no shimmer, DESIGN.md §5).
class SectionSkeleton extends StatelessWidget {
  const SectionSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    Widget bar(double width) => Container(
      width: width,
      height: 10,
      decoration: BoxDecoration(
        color: DelphosColors.surfaceMuted,
        borderRadius: BorderRadius.circular(4),
      ),
    );
    return ExcludeSemantics(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        spacing: 8,
        children: [bar(220), bar(160)],
      ),
    );
  }
}
