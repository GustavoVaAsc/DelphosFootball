/// Whether the sidebar is folded to its icon rail (DESIGN.md §4, Sidebar).
///
/// The state lives in memory for the page's lifetime: it survives navigation
/// between modules but not a reload. The app has no persistence mechanism
/// and adds no dependency for one.
library;

import 'package:flutter/foundation.dart';

/// The sidebar's collapsed flag, shared by every module page.
class SidebarViewModel extends ChangeNotifier {
  bool _collapsed = false;

  /// Whether the sidebar shows the 64 px rail instead of the 240 px column.
  bool get collapsed => _collapsed;

  /// Folds an open sidebar and opens a folded one.
  void toggle() {
    _collapsed = !_collapsed;
    notifyListeners();
  }
}
