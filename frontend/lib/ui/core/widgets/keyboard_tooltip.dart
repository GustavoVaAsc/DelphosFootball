/// A tooltip that also opens when its control gets keyboard focus (a plain
/// tooltip only opens on hover, so a keyboard user would never see the name
/// of an icon-only control). Place it inside a `Pressable`'s builder, whose
/// focus node it follows.
///
/// It opens on a keyboard-driven focus only, not on a click, and on blur it
/// closes only its own tooltip.
library;

import 'package:material_ui/material_ui.dart';

import 'focus_visibility.dart';

/// [child] with a tooltip of [message] on hover and on keyboard focus.
class KeyboardTooltip extends StatefulWidget {
  const KeyboardTooltip({
    super.key,
    required this.message,
    required this.child,
    this.toTheRight = false,
  });

  final String message;
  final Widget child;

  /// Show the tooltip beside the control, to its right, instead of below it
  /// (so on the sidebar rail it does not cover the icons under the control).
  final bool toTheRight;

  @override
  State<KeyboardTooltip> createState() => _KeyboardTooltipState();
}

class _KeyboardTooltipState extends State<KeyboardTooltip> {
  GlobalKey<TooltipState> _key = GlobalKey<TooltipState>();
  bool _focused = false;
  bool _shownByFocus = false;

  @override
  Widget build(BuildContext context) {
    final focused = Focus.maybeOf(context)?.hasFocus ?? false;
    if (focused && !_focused && FocusVisibility.keyboard.value) {
      _shownByFocus = true;
      WidgetsBinding.instance.addPostFrameCallback(
        (_) => _key.currentState?.ensureTooltipVisible(),
      );
    } else if (!focused && _focused && _shownByFocus) {
      _shownByFocus = false;
      // A new key replaces the Tooltip, and its overlay entry goes with it:
      // this one closes and no other tooltip is touched.
      _key = GlobalKey<TooltipState>();
    }
    _focused = focused;
    return Tooltip(
      key: _key,
      message: widget.message,
      excludeFromSemantics: true,
      positionDelegate: widget.toTheRight
          ? (context) => Offset(
              context.target.dx + context.targetSize.width / 2 + 8,
              context.target.dy - context.tooltipSize.height / 2,
            )
          : null,
      child: widget.child,
    );
  }
}
