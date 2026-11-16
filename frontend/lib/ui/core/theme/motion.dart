/// Motion tokens (DESIGN.md §5, dial MOTION 1): one curve, the durations, and
/// the reduced-motion switch every animation goes through.
///
/// What animates, and why:
/// - hover and press feedback (160 ms): confirms the pointer and the click;
/// - the dossier content when the player changes inside an open dossier
///   (180 ms, opacity 0.65 to 1 and 3 px up, as the preview's
///   `dossierEnter`): marks that the panel now shows someone else;
/// - the dossier panel opening and closing (220 ms, 16 px slide from the
///   right plus a fade): shows where the panel comes from and where it goes;
/// - the sidebar folding and unfolding (240 ms): the labels fade before the
///   width shrinks, so text never squashes, and the rail never jumps;
/// - a module page replacing another (200 ms, opacity and 4 px up): marks
///   the change of view;
/// - the dossier's two valuation figures (400 ms, each time a player's
///   valuation loads): draws the eye to the one question the product answers;
/// - table rows and archetype cards on the first load of their view
///   (200 ms each, 30 ms apart): shows the data arriving once.
/// Nothing loops, and nothing else moves: not filters, keystrokes, paging.
library;

import 'package:flutter/widgets.dart';

/// The app's motion values.
abstract final class DelphosMotion {
  /// The preview's `--ease-out`: cubic-bezier(0.16, 1, 0.3, 1).
  static const Curve easeOut = Cubic(0.16, 1, 0.3, 1);

  /// Hover, press and colour feedback.
  static const Duration hover = Duration(milliseconds: 160);

  /// The dossier content swap.
  static const Duration dossierSwap = Duration(milliseconds: 180);

  /// The dossier panel opening and closing.
  static const Duration panel = Duration(milliseconds: 220);

  /// The sidebar folding and unfolding.
  static const Duration sidebar = Duration(milliseconds: 240);

  /// A module page replacing another, and one staggered item's own entry.
  static const Duration enter = Duration(milliseconds: 200);

  /// The two valuation figures counting up.
  static const Duration figures = Duration(milliseconds: 400);

  /// The delay between one staggered item and the next.
  static const Duration stagger = Duration(milliseconds: 30);

  /// [duration], or zero when the platform asks for reduced motion.
  static Duration duration(BuildContext context, Duration duration) =>
      MediaQuery.maybeDisableAnimationsOf(context) ?? false
      ? Duration.zero
      : duration;
}
