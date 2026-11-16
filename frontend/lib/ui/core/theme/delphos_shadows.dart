/// The one shadow of the design (DESIGN.md §5, the preview's
/// `--shadow-float`): `0 1px 2px` in ink at 12%, for layers that float over
/// the page: tooltips, the comparator's suggestions, the chat dialog, select
/// menus and the crest disc over a portrait. Nothing else carries a shadow.
library;

import 'package:flutter/widgets.dart';

import 'delphos_colors.dart';

/// Shadow tokens.
abstract final class DelphosShadows {
  /// `--shadow-float`.
  static const List<BoxShadow> float = [
    BoxShadow(
      color: DelphosColors.floatShadow,
      offset: Offset(0, 1),
      blurRadius: 2,
    ),
  ];
}
