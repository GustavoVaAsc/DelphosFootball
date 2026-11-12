/// The six-size type scale of DESIGN.md §3. No other font size is used.
library;

/// Font sizes in logical pixels, named by their reserved role.
abstract final class TypeScale {
  /// 11: stat labels and axis labels only.
  static const double label = 11;

  /// 12: secondary lines, pills, labels, buttons, footers.
  static const double secondary = 12;

  /// 13: body and table text, controls, navigation.
  static const double body = 13;

  /// 15: section titles, table name and price, stat figures, report prose.
  static const double section = 15;

  /// 20: page title, dossier player name, archetype title.
  static const double title = 20;

  /// 28: the two dossier valuation figures only.
  static const double figure = 28;
}
