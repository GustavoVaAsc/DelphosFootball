/// The colour role of a comparator delta (DESIGN.md §2).
library;

/// Up and down only for output metrics where more is better; everything
/// else is neutral ink-3.
enum DeltaTone { neutral, up, down }
