/// Archetype names by K-Means `cluster_id`, identical to `CLUSTER_LABELS`
/// in `ml/src/delphos_domain/labels.py`. They are proper names published by
/// the clustering stage and keep their capitalisation (DESIGN.md §3).
library;

const Map<int, (String, String)> _archetypes = {
  0: ('Titular Europeo', 'Titulares de Élite y Exposición Europea'),
  1: ('Rotación y Copas', 'Perfiles de Rotación y Copas Nacionales'),
  2: ('Titular de Liga', 'Titulares Regulares de Liga Doméstica'),
};

/// The short name ("Titular Europeo"), or `null` for an unknown cluster.
String? archetypeShortName(int? clusterId) => _archetypes[clusterId]?.$1;

/// The long name ("Titulares de Élite y Exposición Europea"), or `null`.
String? archetypeLongName(int? clusterId) => _archetypes[clusterId]?.$2;

/// One sentence on who a K-Means cluster groups by competitive exposure and
/// match volume, or `null` when unknown.
String? archetypeDescription(int? clusterId) => switch (clusterId) {
  0 =>
    'Titulares consolidados en clubes con participación habitual en torneos '
        'UEFA (27% de sus minutos), alto volumen de juego (2.148\' promedio) '
        'y máxima producción ofensiva por 90 minutos.',
  1 =>
    'Jugadores de rotación y recambio con fuerte proporción de minutos en '
        'copas domésticas (45%), menor minutaje anual (687\' promedio) y rol '
        'de apoyo táctico.',
  2 =>
    'Base de titulares habituales en sus ligas nacionales (72% de titularidad '
        'y 1.536\' promedio) con actividad concentrada casi por completo en el '
        'torneo local.',
  _ => null,
};
