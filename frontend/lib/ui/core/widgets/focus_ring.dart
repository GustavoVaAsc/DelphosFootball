/// The keyboard focus ring of DESIGN.md §2: 2 px wide, 2 px away from the
/// element, in ink (white on the navy sidebar).
library;

import 'package:flutter/widgets.dart';

import '../theme/delphos_colors.dart';

/// Draws the focus ring around [child] while [visible] is true. The ring
/// sits outside the child's box, so showing it never moves the layout.
class FocusRing extends StatelessWidget {
  const FocusRing({
    super.key,
    required this.visible,
    required this.child,
    this.color = DelphosColors.ink,
    this.borderRadius = 0,
  });

  static const double _offset = 2;
  static const double _width = 2;

  final bool visible;
  final Widget child;
  final Color color;

  /// The corner radius of [child]; the ring follows it.
  final double borderRadius;

  @override
  Widget build(BuildContext context) {
    const outset = _offset + _width;
    return Stack(
      clipBehavior: Clip.none,
      children: [
        child,
        if (visible)
          Positioned(
            left: -outset,
            top: -outset,
            right: -outset,
            bottom: -outset,
            child: IgnorePointer(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  border: Border.all(color: color, width: _width),
                  borderRadius: BorderRadius.circular(borderRadius + outset),
                ),
              ),
            ),
          ),
      ],
    );
  }
}
