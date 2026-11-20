/// The six-size type scale of DESIGN.md §3. No other font size is used.
library;

/// Font sizes in logical pixels, named by their reserved role.
abstract final class TypeScale {
  /// 12: stat labels and axis labels only.
  static const double label = 12;

  /// 13: secondary lines, status words, labels, buttons, footers.
  static const double secondary = 13;

  /// 14: body and table text, controls, navigation.
  static const double body = 14;

  /// 16: section titles, table name and price, stat figures, report prose.
  static const double section = 16;

  /// 22: page title, dossier player name, archetype title.
  static const double title = 22;

  /// 30: the two dossier valuation figures only.
  static const double figure = 30;
}
