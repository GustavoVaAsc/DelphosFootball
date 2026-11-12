/// Motion tokens (DESIGN.md §5, dial MOTION 1): one curve, two durations,
/// and the reduced-motion switch every animation goes through.
///
/// What animates, and why:
/// - hover and press feedback (160 ms): confirms the pointer and the click;
/// - the dossier content when the player changes inside an open dossier
///   (180 ms, opacity 0.65 to 1 and 3 px up, as the preview's
///   `dossierEnter`): marks that the panel now shows someone else.
/// Nothing else moves: not filters, keystrokes, page changes, table rows,
/// or opening and closing the dossier.
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

  /// [duration], or zero when the platform asks for reduced motion.
  static Duration duration(BuildContext context, Duration duration) =>
      MediaQuery.maybeDisableAnimationsOf(context) ?? false
      ? Duration.zero
      : duration;
}
