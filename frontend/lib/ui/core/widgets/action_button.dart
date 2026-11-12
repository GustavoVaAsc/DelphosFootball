/// The two button faces of the design preview: primary (ink ground, one
/// per panel, "Reintentar") and secondary (bordered, "Restablecer
/// filtros", "Anterior", "Siguiente").
library;

import 'package:flutter/widgets.dart';

import '../theme/delphos_colors.dart';
import '../theme/delphos_text.dart';
import '../theme/motion.dart';
import '../theme/type_scale.dart';
import 'pressable.dart';

/// A labelled button. `onPressed: null` shows it disabled at half opacity.
class ActionButton extends StatelessWidget {
  const ActionButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.primary = false,
  });

  final String label;
  final VoidCallback? onPressed;

  /// Ink ground and white text, for the one main action of a panel.
  final bool primary;

  static const double _radius = 7;

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null;
    return Opacity(
      opacity: enabled ? 1 : 0.5,
      child: Pressable(
        onPressed: onPressed,
        semanticLabel: label,
        borderRadius: _radius,
        builder: (context, hovered) => AnimatedContainer(
          // Hover feedback (DESIGN.md §5); instant under reduced motion.
          duration: DelphosMotion.duration(context, DelphosMotion.hover),
          curve: DelphosMotion.easeOut,
          height: primary ? 32 : 30,
          padding: EdgeInsets.symmetric(horizontal: primary ? 14 : 12),
          decoration: BoxDecoration(
            color: primary
                ? (hovered ? DelphosColors.sidebarActive : DelphosColors.ink)
                : (hovered
                      ? DelphosColors.surfaceSubtle
                      : DelphosColors.surface),
            borderRadius: BorderRadius.circular(_radius),
            border: Border.all(
              color: primary
                  ? DelphosColors.ink
                  : (hovered
                        ? DelphosColors.ink2
                        : DelphosColors.controlBorder),
            ),
          ),
          // Hugs its label: a Center with widthFactor 1 never stretches to
          // the width of a column or panel.
          child: Center(
            widthFactor: 1,
            child: Text(
              label,
              maxLines: 1,
              softWrap: false,
              style: DelphosText.ui(
                size: TypeScale.secondary,
                weight: primary ? FontWeight.w600 : FontWeight.w500,
                color: primary ? DelphosColors.surface : DelphosColors.ink,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
