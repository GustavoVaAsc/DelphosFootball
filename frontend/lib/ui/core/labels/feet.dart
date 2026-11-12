/// Spanish labels for a player's preferred foot (design preview
/// `FOOT_LABELS`).
library;

/// "Diestro", "Zurdo" or "Ambidiestro", or `null` when unknown.
String? footLabel(String? foot) => switch (foot) {
  'right' => 'Diestro',
  'left' => 'Zurdo',
  'both' => 'Ambidiestro',
  _ => null,
};
