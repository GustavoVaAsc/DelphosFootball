/// The states of one dossier section (identity, valuation, replacements).
library;

/// What a section shows for its player.
enum SectionStatus {
  /// The data is being fetched: a static skeleton.
  loading,

  /// The data is shown.
  ready,

  /// The backend has nothing for this player (a 404 on replacements or
  /// valuation): a plain sentence, not an error.
  absent,

  /// The request failed; the section offers a retry.
  error,
}
