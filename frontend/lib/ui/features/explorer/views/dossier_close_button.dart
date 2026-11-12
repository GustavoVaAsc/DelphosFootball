/// The dossier header's one action: a 32 x 32 secondary icon button with a
/// 14 px × (DESIGN.md §4), named "Cerrar ficha" for screen readers.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/motion.dart';
import '../../../core/widgets/line_glyph.dart';
import '../../../core/widgets/pressable.dart';

/// Closes the dossier.
class DossierCloseButton extends StatelessWidget {
  const DossierCloseButton({super.key, required this.onPressed});

  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onPressed: onPressed,
      semanticLabel: 'Cerrar ficha',
      borderRadius: 7,
      builder: (context, hovered) => AnimatedContainer(
        // Hover feedback (DESIGN.md §5).
        duration: DelphosMotion.duration(context, DelphosMotion.hover),
        curve: DelphosMotion.easeOut,
        width: 32,
        height: 32,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: hovered ? DelphosColors.surfaceSubtle : DelphosColors.surface,
          borderRadius: BorderRadius.circular(7),
          border: Border.all(
            color: hovered ? DelphosColors.ink2 : DelphosColors.controlBorder,
          ),
        ),
        child: const LineGlyph.close(),
      ),
    );
  }
}
