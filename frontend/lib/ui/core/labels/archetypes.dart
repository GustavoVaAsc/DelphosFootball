/// Archetype names by K-Means `cluster_id`, identical to `CLUSTER_LABELS`
/// in `ml/src/delphos_domain/labels.py`. They are proper names published by
/// the clustering stage and keep their capitalisation (DESIGN.md §3).
library;

const Map<int, (String, String)> _archetypes = {
  0: ('Creador Ofensivo', 'Creadores Ofensivos y Finalizadores'),
  1: ('Box-to-Box', 'Todocampistas Box-to-Box y Carrileros'),
  2: ('Ancla Defensiva', 'Anclas Defensivas y Especialistas de Contención'),
};

/// The short name ("Creador Ofensivo"), or `null` for an unknown cluster.
String? archetypeShortName(int? clusterId) => _archetypes[clusterId]?.$1;

/// The long name ("Creadores Ofensivos y Finalizadores"), or `null`.
String? archetypeLongName(int? clusterId) => _archetypes[clusterId]?.$2;

/// One sentence on who an archetype groups, as the design preview's
/// `es_desc` (app copy keyed by `cluster_id`), or `null` when unknown.
String? archetypeDescription(int? clusterId) => switch (clusterId) {
  0 =>
    'Delanteros, extremos y mediapuntas con alta producción de goles y '
        'asistencias por partido y peso determinante en el último tercio.',
  1 =>
    'Mediocampistas interiores, volantes de recorrido y laterales de '
        'proyección con equilibrio entre despliegue físico, apoyo y transición.',
  2 =>
    'Defensas centrales, pivotes posicionales y zagueros cuyo valor radica '
        'en sostener porterías imbatidas y minimizar goles recibidos.',
  _ => null,
};
