/// When focus rings show: the CSS `:focus-visible` rule for the whole app.
///
/// Flutter's `FocusManager.highlightMode` switches to traditional on a key
/// press but never back on a mouse click, so on a desktop browser a ring
/// would stay on whatever a click focused (a row name, the table area). This
/// tracks the last input instead: a key press shows rings, a pointer press
/// hides them, until the next key press.
library;

import 'package:flutter/foundation.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';

/// Whether the last input was the keyboard.
class FocusVisibility {
  FocusVisibility._();

  static final ValueNotifier<bool> _keyboard = ValueNotifier(false);
  static bool _installed = false;

  /// True after a key press, false after a pointer press.
  static ValueListenable<bool> get keyboard => _keyboard;

  /// Starts listening to the keyboard and to every pointer press. Safe to
  /// call more than once.
  static void install() {
    if (_installed) return;
    _installed = true;
    HardwareKeyboard.instance.addHandler(_onKey);
    GestureBinding.instance.pointerRouter.addGlobalRoute(_onPointer);
  }

  static bool _onKey(KeyEvent event) {
    if (event is KeyDownEvent) _keyboard.value = true;
    return false;
  }

  static void _onPointer(PointerEvent event) {
    if (event is PointerDownEvent) _keyboard.value = false;
  }
}
