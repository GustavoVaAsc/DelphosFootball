/// One module icon of the collapsed sidebar rail (DESIGN.md §4, Sidebar).
library;

import 'package:material_ui/material_ui.dart';

import '../theme/delphos_colors.dart';
import '../theme/delphos_radius.dart';
import '../theme/motion.dart';
import '../widgets/keyboard_tooltip.dart';
import '../widgets/pressable.dart';

/// A 40 px square module button for the rail: the glyph on the active or
/// hover ground, and the module name as the semantics label and in a tooltip
/// that opens on hover and on keyboard focus.
class RailItem extends StatelessWidget {
  const RailItem({
    super.key,
    required this.label,
    required this.active,
    required this.onSelected,
    required this.glyph,
  });

  static const double _radius = DelphosRadius.inset;
  static const Color _clear = Color(0x00000000);

  final String label;
  final bool active;
  final VoidCallback onSelected;

  /// Draws the module's glyph in the colour for the current state.
  final Widget Function(Color color) glyph;

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onPressed: onSelected,
      semanticLabel: label,
      selected: active,
      focusRingColor: DelphosColors.onSidebar,
      borderRadius: _radius,
      builder: (context, hovered) => KeyboardTooltip(
        message: label,
        toTheRight: true,
        child: AnimatedContainer(
          // Hover feedback (DESIGN.md §5); instant under reduced motion.
          duration: DelphosMotion.duration(context, DelphosMotion.hover),
          curve: DelphosMotion.easeOut,
          width: 40,
          height: 40,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: active
                ? DelphosColors.sidebarActive
                : (hovered ? DelphosColors.sidebarHover : _clear),
            borderRadius: BorderRadius.circular(_radius),
          ),
          child: glyph(
            active || hovered
                ? DelphosColors.onSidebar
                : DelphosColors.sidebarText,
          ),
        ),
      ),
    );
  }
}
