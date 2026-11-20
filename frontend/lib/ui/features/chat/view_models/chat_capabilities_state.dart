/// Visibility of the capabilities pop-up: open by itself on the first visit
/// after a page load (`ChatIntroGate`), and reopened from the header.
library;

import 'package:flutter/foundation.dart';

import 'chat_intro_gate.dart';

/// The pop-up's open flag and its two actions, for a [ChangeNotifier].
mixin ChatCapabilitiesState on ChangeNotifier {
  bool _isCapabilitiesOpen = ChatIntroGate.takeFirstVisit();

  bool get isCapabilitiesOpen => _isCapabilitiesOpen;

  void openCapabilities() => _setCapabilitiesOpen(true);

  void closeCapabilities() => _setCapabilitiesOpen(false);

  void _setCapabilitiesOpen(bool open) {
    if (_isCapabilitiesOpen == open) return;
    _isCapabilitiesOpen = open;
    notifyListeners();
  }
}
