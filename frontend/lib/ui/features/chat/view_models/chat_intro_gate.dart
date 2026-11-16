/// Remembers, for the life of the page, that the capabilities pop-up was shown.
library;

/// In-memory flag: the pop-up opens by itself on the first `/chat` visit
/// after a page load and stays closed on later visits.
abstract final class ChatIntroGate {
  static bool _shown = false;

  /// Returns whether the pop-up should open now, and marks it as shown.
  static bool takeFirstVisit() {
    final first = !_shown;
    _shown = true;
    return first;
  }

  /// Forgets the flag, so each test starts as a fresh page load.
  static void reset() => _shown = false;
}
