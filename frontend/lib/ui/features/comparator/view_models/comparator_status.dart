/// The states of the comparator page (DESIGN.md §7).
library;

/// What the comparator shows.
enum ComparatorStatus {
  /// No player chosen yet: the selector and one plain line.
  idle,

  /// The reference is loading: a static skeleton table.
  loading,

  /// The table is shown.
  ready,

  /// The reference could not be loaded: one panel with "Reintentar".
  error,
}
