/// The one tappable primitive of the app: keyboard activation, hover and
/// press state, button semantics and the DESIGN.md §2 focus ring, so every
/// control behaves and looks the same under mouse, keyboard and screen
/// reader.
library;

import 'package:flutter/widgets.dart';

import '../theme/delphos_colors.dart';
import '../theme/motion.dart';
import 'focus_ring.dart';
import 'focus_visibility.dart';

/// Builds the control's look from whether the pointer is over it.
typedef PressableBuilder = Widget Function(BuildContext context, bool hovered);

/// A focusable, keyboard-activatable control that draws its focus ring.
///
/// Activation paths, all of which call [onPressed]:
/// - a click or tap;
/// - Space and Enter: `ActivateIntent` everywhere, and `ButtonActivateIntent`,
///   which is what Flutter web binds Enter to (WidgetsApp's web shortcuts);
/// - a semantics tap, which is how a browser click or a screen reader
///   reaches the control once the semantics tree is on.
///
/// The ring shows only while the control has focus and the last input was
/// the keyboard ([FocusVisibility]), like CSS `:focus-visible`.
class Pressable extends StatefulWidget {
  const Pressable({
    super.key,
    required this.onPressed,
    required this.semanticLabel,
    required this.builder,
    this.selected,
    this.expanded,
    this.focusNode,
    this.focusRingColor = DelphosColors.ink,
    this.borderRadius = 0,
    this.pressedScale = 0.985,
  });

  /// `null` disables the control: not focusable, no cursor, no action.
  final VoidCallback? onPressed;

  /// The accessible name; the visual child is excluded from semantics.
  final String semanticLabel;
  final PressableBuilder builder;

  /// Whether the control is the current choice (nav item, segment).
  final bool? selected;

  /// Whether the control's panel is open (a row name and its dossier).
  final bool? expanded;
  final FocusNode? focusNode;

  /// Ink on light grounds, white on the navy sidebar.
  final Color focusRingColor;
  final double borderRadius;

  /// Press feedback, as the preview's `button:active { scale(0.985) }`;
  /// 1 turns it off (a row name is text, not a button face).
  final double pressedScale;

  @override
  State<Pressable> createState() => _PressableState();
}

class _PressableState extends State<Pressable> {
  bool _hovered = false;
  bool _pressed = false;
  bool _focused = false;

  bool get _enabled => widget.onPressed != null;

  void _activate() => widget.onPressed?.call();

  Object? _invoke(Intent _) {
    _activate();
    return null;
  }

  void _setPressed(bool value) {
    if (_pressed != value) setState(() => _pressed = value);
  }

  @override
  Widget build(BuildContext context) {
    // A container, so the control is its own node and is never merged
    // into a labelled ancestor (a dossier, a filter group).
    return Semantics(
      container: true,
      button: true,
      enabled: _enabled,
      selected: widget.selected,
      expanded: widget.expanded,
      label: widget.semanticLabel,
      onTap: _enabled ? _activate : null,
      excludeSemantics: true,
      child: FocusableActionDetector(
        enabled: _enabled,
        focusNode: widget.focusNode,
        mouseCursor: _enabled ? SystemMouseCursors.click : MouseCursor.defer,
        onShowHoverHighlight: (value) => setState(() => _hovered = value),
        onFocusChange: (value) => setState(() => _focused = value),
        actions: {
          ActivateIntent: CallbackAction<ActivateIntent>(onInvoke: _invoke),
          ButtonActivateIntent: CallbackAction<ButtonActivateIntent>(
            onInvoke: _invoke,
          ),
        },
        child: GestureDetector(
          onTap: _enabled ? _activate : null,
          onTapDown: _enabled ? (_) => _setPressed(true) : null,
          onTapUp: (_) => _setPressed(false),
          onTapCancel: () => _setPressed(false),
          // Press feedback (DESIGN.md §5): confirms the click landed. Off
          // under reduced motion.
          child: AnimatedScale(
            scale: _pressed ? widget.pressedScale : 1,
            duration: DelphosMotion.duration(context, DelphosMotion.hover),
            curve: DelphosMotion.easeOut,
            child: ValueListenableBuilder<bool>(
              valueListenable: FocusVisibility.keyboard,
              builder: (context, keyboard, child) => FocusRing(
                visible: _focused && keyboard && _enabled,
                color: widget.focusRingColor,
                borderRadius: widget.borderRadius,
                child: child!,
              ),
              child: widget.builder(context, _hovered && _enabled),
            ),
          ),
        ),
      ),
    );
  }
}
