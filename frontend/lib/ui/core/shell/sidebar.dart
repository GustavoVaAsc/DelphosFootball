/// The navy sidebar: header with the hamburger button and the four module
/// links (DESIGN.md §4, Sidebar). Open it is a 240 px column of text items
/// with the data footer; folded it is a 64 px rail of the hamburger and one
/// icon per module. The hamburger folds it.
///
/// Motion (DESIGN.md §5): folding takes 240 ms on one timeline. First the
/// open content fades out at the full 240 px, so no label is squashed or
/// wraps; then the width eases down to 64 px while the icons fade in.
/// Unfolding runs the same timeline backwards. The hamburger never fades or
/// moves.
/// Instant under reduced motion.
library;

import 'package:flutter/widgets.dart';
import 'package:provider/provider.dart';

import '../theme/delphos_colors.dart';
import '../theme/motion.dart';
import '../view_models/sidebar_view_model.dart';
import 'sidebar_brand_header.dart';
import 'sidebar_footer.dart';
import 'sidebar_modules.dart';

/// The navigation column or, folded, the rail.
class Sidebar extends StatefulWidget {
  const Sidebar({super.key, required this.location});

  static const double width = 240;
  static const double railWidth = 64;

  /// Where on the 0 (open) to 1 (folded) timeline the open content has
  /// finished fading out and the width starts to shrink.
  static const double _widthStart = 0.4;

  /// Where the rail's icons have finished fading in.
  static const double _railShown = 0.7;

  /// The current path, which decides the active item.
  final String location;

  @override
  State<Sidebar> createState() => _SidebarState();
}

class _SidebarState extends State<Sidebar> with SingleTickerProviderStateMixin {
  late final AnimationController _fold = AnimationController(vsync: this);
  late final SidebarViewModel _sidebar;
  bool _bound = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _fold.duration = DelphosMotion.duration(context, DelphosMotion.sidebar);
    if (_bound) return;
    _bound = true;
    _sidebar = context.read<SidebarViewModel>();
    _fold.value = _sidebar.collapsed ? 1 : 0;
    _sidebar.addListener(_onToggle);
  }

  void _onToggle() {
    if (_sidebar.collapsed) {
      _fold.forward();
    } else {
      _fold.reverse();
    }
  }

  @override
  void dispose() {
    if (_bound) _sidebar.removeListener(_onToggle);
    _fold.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _fold,
      builder: (context, _) {
        final t = _fold.value;
        final rail = t >= Sidebar._widthStart;
        final widthT = ((t - Sidebar._widthStart) / (1 - Sidebar._widthStart))
            .clamp(0.0, 1.0);
        final width =
            Sidebar.width -
            (Sidebar.width - Sidebar.railWidth) *
                DelphosMotion.easeOut.transform(widthT);
        // The labels (open) or the icons (rail), dipping to zero at the
        // switch so the content never changes shape while visible.
        final opacity = rail
            ? ((t - Sidebar._widthStart) /
                      (Sidebar._railShown - Sidebar._widthStart))
                  .clamp(0.0, 1.0)
            : (1 - t / Sidebar._widthStart).clamp(0.0, 1.0);
        return Container(
          width: width,
          color: DelphosColors.sidebarBg,
          child: ClipRect(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                SidebarBrandHeader(collapsed: rail, labelOpacity: opacity),
                Opacity(
                  opacity: opacity,
                  child: SidebarModules(location: widget.location, rail: rail),
                ),
                const Spacer(),
                // Open only: it is text, and the rail has no room for it.
                if (!rail)
                  Opacity(opacity: opacity, child: const SidebarFooter()),
              ],
            ),
          ),
        );
      },
    );
  }
}
