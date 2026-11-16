/// The corner-radius scale (DESIGN.md §5): every rounded corner of the app is
/// one of these values.
library;

/// Corner radii in logical pixels.
abstract final class DelphosRadius {
  /// Cards, panels and tables.
  static const double card = 10;

  /// The clip inside a bordered [card]: one pixel less, so the border shows.
  static const double cardInner = 9;

  /// The sidebar's items, the menu button and the archetype pitch ground.
  static const double inset = 8;

  /// Controls: inputs, selects, the segmented frame, the close button.
  static const double control = 7;

  /// A segment inside a control, the Estado segments.
  static const double segment = 5;

  /// Static skeleton blocks.
  static const double bar = 4;

  /// Tooltips.
  static const double tooltip = 6;

  /// Small marks: the share bar, the pitch glyph ground.
  static const double small = 3;

  /// Text links, legend swatches and the flag frame.
  static const double hairline = 2;
}
