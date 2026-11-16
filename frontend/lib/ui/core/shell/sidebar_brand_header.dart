/// The sidebar's 60 px brand header (DESIGN.md §4, Sidebar): the hamburger
/// button at the left, then the two-line name while the sidebar is open. The
/// button is 36 px with 14 px at its left, so it is centred on the 64 px rail
/// and does not move while the sidebar folds.
library;

import 'package:flutter/widgets.dart';

import '../theme/delphos_colors.dart';
import '../theme/delphos_text.dart';
import '../theme/type_scale.dart';
import 'menu_button.dart';

/// The menu button with, when the sidebar is open, the product name.
class SidebarBrandHeader extends StatelessWidget {
  const SidebarBrandHeader({
    super.key,
    required this.collapsed,
    this.labelOpacity = 1,
  });

  final bool collapsed;

  /// The name's opacity while the sidebar folds or unfolds; the button stays.
  final double labelOpacity;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 60,
      // (64 - 36) / 2 = 14 on the rail, kept in both states.
      padding: const EdgeInsets.only(left: 14, right: 14),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: DelphosColors.sidebarRule)),
      ),
      child: Row(
        spacing: 12,
        children: [
          const MenuButton(),
          if (!collapsed)
            Expanded(
              child: Opacity(
                opacity: labelOpacity,
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'DelphosFootball',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: DelphosText.ui(
                        size: TypeScale.section,
                        weight: FontWeight.w700,
                        color: DelphosColors.onSidebar,
                        height: 1.15,
                      ),
                    ),
                    Text(
                      'Dirección Deportiva',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: DelphosText.ui(
                        size: TypeScale.secondary,
                        weight: FontWeight.w500,
                        color: DelphosColors.sidebarMuted,
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}
