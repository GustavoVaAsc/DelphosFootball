/// The sidebar's four module links (DESIGN.md §4, Sidebar): text items while
/// it is open, icon buttons on the rail.
library;

import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

import '../../../routing/routes.dart';
import 'nav_glyph.dart';
import 'nav_item.dart';
import 'rail_item.dart';

/// The module list for the current [location].
class SidebarModules extends StatelessWidget {
  const SidebarModules({super.key, required this.location, required this.rail});

  /// The current path, which decides the active item.
  final String location;

  /// Whether to show the icon rail instead of the text items.
  final bool rail;

  static final List<(String, String, Widget Function(Color))> _modules = [
    (
      'Explorador de Mercado',
      Routes.explorer,
      (color) => NavGlyph.explorer(color: color),
    ),
    (
      'Comparador Moneyball',
      Routes.comparator,
      (color) => NavGlyph.comparator(color: color),
    ),
    (
      'Arquetipos Tácticos',
      Routes.archetypes,
      (color) => NavGlyph.archetypes(color: color),
    ),
    ('PitIA', Routes.chat, (color) => NavGlyph.assistant(color: color)),
  ];

  bool _isActive(String path) =>
      location == path || location.startsWith('$path/');

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      label: 'Módulos principales',
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 20),
        child: Column(
          // Left-aligned, so the icons stay put while the width changes.
          crossAxisAlignment: CrossAxisAlignment.start,
          spacing: 4,
          children: [
            for (final (label, path, glyph) in _modules)
              if (rail)
                RailItem(
                  label: label,
                  active: _isActive(path),
                  onSelected: () => context.go(path),
                  glyph: glyph,
                )
              else
                NavItem(
                  label: label,
                  active: _isActive(path),
                  onSelected: () => context.go(path),
                ),
          ],
        ),
      ),
    );
  }
}
