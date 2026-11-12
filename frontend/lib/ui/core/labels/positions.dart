/// Spanish labels for a player's broad position and sub-position, copied
/// from the design preview's `POS_LABELS` and `SUBPOS_LABELS`.
///
/// Sub-positions are in sentence case (DESIGN.md §3 "Case"). An unknown key
/// returns `null`, so raw English never reaches the screen; the caller
/// decides what to omit.
library;

const Map<String, String> _positions = {
  'Attack': 'Ataque',
  'Midfield': 'Mediocampo',
  'Defender': 'Defensa',
};

const Map<String, String> _subPositions = {
  'Centre-Forward': 'Delantero centro',
  'Right Winger': 'Extremo derecho',
  'Left Winger': 'Extremo izquierdo',
  'Second Striker': 'Segundo delantero',
  'Attacking Midfield': 'Mediapunta',
  'Central Midfield': 'Mediocentro',
  'Defensive Midfield': 'Pivote defensivo',
  'Right Midfield': 'Interior derecho',
  'Left Midfield': 'Interior izquierdo',
  'Centre-Back': 'Defensa central',
  'Right-Back': 'Lateral derecho',
  'Left-Back': 'Lateral izquierdo',
};

/// "Ataque", "Mediocampo" or "Defensa", or `null` when unknown.
String? positionLabel(String? position) => _positions[position];

/// The Spanish sub-position ("Extremo derecho"), or `null` when unknown.
String? subPositionLabel(String? subPosition) => _subPositions[subPosition];

/// The role to print: the sub-position when known, else the position.
String? roleLabel({String? position, String? subPosition}) =>
    subPositionLabel(subPosition) ?? positionLabel(position);
