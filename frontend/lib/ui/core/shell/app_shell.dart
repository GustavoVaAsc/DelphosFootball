/// The app frame: sidebar, top bar and the routed page (DESIGN.md §4,
/// Shell). Full height, no page-level scroll; each page scrolls inside.
library;

import 'package:material_ui/material_ui.dart';

import '../../../routing/routes.dart';
import '../theme/delphos_colors.dart';
import 'sidebar.dart';
import 'top_bar.dart';

/// Wraps every module page in the sidebar and top bar.
class AppShell extends StatelessWidget {
  const AppShell({super.key, required this.location, required this.child});

  /// The current path; it picks the active module and the title.
  final String location;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    // Title sets the browser tab title per module (DESIGN.md: one module,
    // one title); it is deeper than MaterialApp's own, so it wins.
    return Title(
      title: Routes.documentTitleFor(location),
      color: DelphosColors.ink,
      child: Scaffold(
        backgroundColor: DelphosColors.canvas,
        body: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Two traversal groups: Tab walks the whole sidebar, then the
            // page. Without them, reading order would interleave the nav
            // items with the page controls at the same height.
            FocusTraversalGroup(child: Sidebar(location: location)),
            Expanded(
              child: FocusTraversalGroup(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    TopBar(title: Routes.titleFor(location) ?? ''),
                    Expanded(child: child),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
