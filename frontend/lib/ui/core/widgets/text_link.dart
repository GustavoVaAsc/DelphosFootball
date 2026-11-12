/// A quiet text link in ink, the design's secondary action ("Ver en el
/// explorador", "Ir al Explorador de Mercado").
library;

import 'package:flutter/widgets.dart';

import '../theme/delphos_colors.dart';
import '../theme/delphos_text.dart';
import 'pressable.dart';

/// Ink text, underlined on hover, with the ink focus ring.
class TextLink extends StatelessWidget {
  const TextLink({super.key, required this.label, required this.onPressed});

  final String label;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onPressed: onPressed,
      semanticLabel: label,
      borderRadius: 2,
      builder: (context, hovered) => Text(
        label,
        style: DelphosText.ui(weight: FontWeight.w500).copyWith(
          decoration: hovered ? TextDecoration.underline : null,
          decorationColor: DelphosColors.ink,
        ),
      ),
    );
  }
}
