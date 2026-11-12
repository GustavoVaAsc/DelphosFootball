/// The dossier header while the profile loads: static blocks in the shape
/// of the portrait, the name and the club line (no shimmer, DESIGN.md §5).
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';

/// A placeholder for `DossierHeader`.
class DossierHeaderSkeleton extends StatelessWidget {
  const DossierHeaderSkeleton({super.key});

  static Widget _block(double width, double height, double radius) => Container(
    width: width,
    height: height,
    decoration: BoxDecoration(
      color: DelphosColors.surfaceMuted,
      borderRadius: BorderRadius.circular(radius),
    ),
  );

  @override
  Widget build(BuildContext context) {
    return ExcludeSemantics(
      child: Row(
        spacing: 14,
        children: [
          _block(64, 64, 32),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            spacing: 10,
            children: [_block(160, 14, 4), _block(220, 10, 4)],
          ),
        ],
      ),
    );
  }
}
