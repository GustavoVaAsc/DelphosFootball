/// The hamburger button at the top left of the sidebar, where the brand mark
/// used to be (DESIGN.md §4, Sidebar): it folds the sidebar to its rail and
/// opens it again. It is the same 36 px button in the same place, centred on
/// the 64 px rail, whether the sidebar is open or folded; only its Spanish
/// label changes ("Plegar menú" open, "Desplegar menú" folded). It is drawn
/// for the navy sidebar: a `--sidebar-text` glyph, white on hover, the
/// `--sidebar-active` hover ground and the white focus ring.
library;

import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../theme/delphos_colors.dart';
import '../theme/delphos_radius.dart';
import '../theme/motion.dart';
import '../view_models/sidebar_view_model.dart';
import '../widgets/keyboard_tooltip.dart';
import '../widgets/pressable.dart';
import 'nav_glyph.dart';

/// Toggles the shared [SidebarViewModel].
class MenuButton extends StatelessWidget {
  const MenuButton({super.key});

  static const double size = 36;
  static const double _radius = DelphosRadius.inset;
  static const Color _clear = Color(0x00000000);

  @override
  Widget build(BuildContext context) {
    final sidebar = context.watch<SidebarViewModel>();
    final label = sidebar.collapsed ? 'Desplegar menú' : 'Plegar menú';
    return Pressable(
      onPressed: sidebar.toggle,
      semanticLabel: label,
      expanded: !sidebar.collapsed,
      focusRingColor: DelphosColors.onSidebar,
      borderRadius: _radius,
      builder: (context, hovered) => KeyboardTooltip(
        message: label,
        toTheRight: true,
        child: AnimatedContainer(
          // Hover feedback (DESIGN.md §5); instant under reduced motion.
          duration: DelphosMotion.duration(context, DelphosMotion.hover),
          curve: DelphosMotion.easeOut,
          width: size,
          height: size,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: hovered ? DelphosColors.sidebarActive : _clear,
            borderRadius: BorderRadius.circular(_radius),
          ),
          child: NavGlyph.menu(
            color: hovered
                ? DelphosColors.onSidebar
                : DelphosColors.sidebarText,
          ),
        ),
      ),
    );
  }
}
