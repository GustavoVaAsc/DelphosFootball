/// A quiet text link in ink, the design's secondary action ("Ver en el
/// explorador", "Ir al Explorador de Mercado").
library;

import 'package:flutter/widgets.dart';

import '../theme/delphos_colors.dart';
import '../theme/delphos_radius.dart';
import '../theme/delphos_text.dart';
import 'pressable.dart';

/// Ink text, always underlined (the underline darkens on hover), with the ink
/// focus ring.
class TextLink extends StatelessWidget {
  const TextLink({super.key, required this.label, required this.onPressed});

  final String label;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onPressed: onPressed,
      semanticLabel: label,
      borderRadius: DelphosRadius.hairline,
      builder: (context, hovered) => Text(
        label,
        // Always underlined, as in the preview: a quiet control-border
        // underline at rest, ink on hover.
        style: DelphosText.ui(weight: FontWeight.w500).copyWith(
          decoration: TextDecoration.underline,
          decorationColor: hovered
              ? DelphosColors.ink
              : DelphosColors.controlBorder,
        ),
      ),
    );
  }
}
