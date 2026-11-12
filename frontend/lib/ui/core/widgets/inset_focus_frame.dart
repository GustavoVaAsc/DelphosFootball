/// A focus target drawn inside its box: for a scroll area inside a card
/// that clips, where the usual outside ring would be cut off (the preview's
/// `outline-offset: -2px` on the table scroller).
library;

import 'package:flutter/widgets.dart';

import '../theme/delphos_colors.dart';
import 'focus_visibility.dart';

/// Makes [child] focusable through [focusNode] (programmatically only: it is
/// not a Tab stop and not a semantics focus target, so a browser click in
/// the area cannot focus it) and draws a 2 px ink frame while it has focus
/// and the last input was the keyboard.
class InsetFocusFrame extends StatelessWidget {
  const InsetFocusFrame({
    super.key,
    required this.focusNode,
    required this.child,
  });

  final FocusNode focusNode;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Focus(
      focusNode: focusNode,
      skipTraversal: true,
      includeSemantics: false,
      child: ListenableBuilder(
        listenable: Listenable.merge([focusNode, FocusVisibility.keyboard]),
        builder: (context, child) => Container(
          foregroundDecoration:
              focusNode.hasPrimaryFocus && FocusVisibility.keyboard.value
              ? BoxDecoration(
                  border: Border.all(color: DelphosColors.ink, width: 2),
                )
              : null,
          child: child,
        ),
        child: child,
      ),
    );
  }
}
