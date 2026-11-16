/// Remembers which views have already had their first load, so the staggered
/// entry (DESIGN.md §5) plays once per page load of the app and never when
/// the user returns to a view. In memory only, like the sidebar's state.
library;

/// One claim per view name.
class FirstLoadTracker {
  final Set<String> _claimed = {};

  /// True the first time [view] is claimed, false every time after.
  bool claim(String view) => _claimed.add(view);
}
