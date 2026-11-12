/// One text item of the sidebar navigation (DESIGN.md §4, Sidebar).
library;

import 'package:flutter/widgets.dart';

import '../theme/delphos_colors.dart';
import '../theme/delphos_text.dart';
import '../theme/motion.dart';
import '../widgets/pressable.dart';

/// A sidebar module link with the white focus ring of the navy sidebar.
/// The weight never changes between states, so a label never reflows:
/// active and hover differ only in ground and colour.
class NavItem extends StatelessWidget {
  const NavItem({
    super.key,
    required this.label,
    required this.active,
    required this.onSelected,
  });

  static const double _radius = 8;
  static const Color _clear = Color(0x00000000);

  final String label;
  final bool active;
  final VoidCallback onSelected;

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onPressed: onSelected,
      semanticLabel: label,
      selected: active,
      focusRingColor: DelphosColors.onSidebar,
      borderRadius: _radius,
      builder: (context, hovered) => AnimatedContainer(
        // Hover feedback (DESIGN.md §5); instant under reduced motion.
        duration: DelphosMotion.duration(context, DelphosMotion.hover),
        curve: DelphosMotion.easeOut,
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
        decoration: BoxDecoration(
          color: active
              ? DelphosColors.sidebarActive
              : (hovered ? DelphosColors.sidebarHover : _clear),
          borderRadius: BorderRadius.circular(_radius),
        ),
        child: Text(
          label,
          maxLines: 1,
          softWrap: false,
          style: DelphosText.ui(
            weight: FontWeight.w500,
            height: 1.3,
            color: active || hovered
                ? DelphosColors.onSidebar
                : DelphosColors.sidebarText,
          ),
        ),
      ),
    );
  }
}
