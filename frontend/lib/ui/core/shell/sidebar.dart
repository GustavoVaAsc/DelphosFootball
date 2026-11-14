/// The navy sidebar: brand header and the four module links
/// (DESIGN.md §4, Sidebar). The data footer arrives with the explorer data.
library;

import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

import '../../../routing/routes.dart';
import '../brand/pitch_mark.dart';
import '../theme/delphos_colors.dart';
import '../theme/delphos_text.dart';
import '../theme/type_scale.dart';
import 'nav_item.dart';
import 'sidebar_footer.dart';

/// The 240 px navigation column.
class Sidebar extends StatelessWidget {
  const Sidebar({super.key, required this.location});

  static const double width = 240;

  static const List<(String, String)> _modules = [
    ('Explorador de Mercado', Routes.explorer),
    ('Comparador Moneyball', Routes.comparator),
    ('Arquetipos Tácticos', Routes.archetypes),
    ('Asistente de Scouting', Routes.chat),
  ];

  /// The current path, which decides the active item.
  final String location;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      color: DelphosColors.sidebarBg,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const _BrandHeader(),
          Semantics(
            container: true,
            label: 'Módulos principales',
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 20),
              child: Column(
                spacing: 4,
                children: [
                  for (final (label, path) in _modules)
                    NavItem(
                      label: label,
                      active: location == path || location.startsWith('$path/'),
                      onSelected: () => context.go(path),
                    ),
                ],
              ),
            ),
          ),
          const Spacer(),
          const SidebarFooter(),
        ],
      ),
    );
  }
}

class _BrandHeader extends StatelessWidget {
  const _BrandHeader();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 60,
      padding: const EdgeInsets.symmetric(horizontal: 18),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: DelphosColors.sidebarRule)),
      ),
      child: Row(
        spacing: 11,
        children: [
          const PitchMark(),
          Expanded(
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
        ],
      ),
    );
  }
}
