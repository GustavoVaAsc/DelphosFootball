/// The four states of the market table (DESIGN.md §7).
library;

/// What the table shows.
enum ExplorerStatus {
  /// The first page is being fetched: static skeleton rows.
  loading,

  /// Rows are shown.
  ready,

  /// The filters match nobody.
  empty,

  /// The server could not be reached or answered with an error.
  error,
}
