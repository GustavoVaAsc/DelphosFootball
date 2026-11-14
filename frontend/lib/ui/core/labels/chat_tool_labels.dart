/// Natural Spanish descriptions for the conversational agent's tool steps.
///
/// Translates backend tool identifiers into natural Spanish phrases so literal
/// function names never reach the scouting UI.
library;

const Map<String, String> _stepTitles = {
  'search_players': 'Búsqueda de jugadores en el mercado',
  'get_player_profile': 'Consulta de perfil y estadísticas',
  'get_player_valuation': 'Análisis de valoración y brecha',
  'get_player_replacements': 'Evaluación de reemplazos tácticos',
  'get_cluster_summary': 'Consulta de arquetipos tácticos',
};

const Map<String, String> _fallbackSummaries = {
  'search_players': 'Se consultó el catálogo de jugadores del modelo.',
  'get_player_profile': 'Se revisó el perfil deportivo y la temporada activa.',
  'get_player_valuation':
      'Se revisó el valor estimado y la decisión de los modelos.',
  'get_player_replacements':
      'Se compararon candidatos de reemplazo compatibles.',
  'get_cluster_summary':
      'Se consultaron las métricas de los arquetipos K-Means.',
};

final RegExp _literalToolPattern = RegExp(
  r'search_players|get_player_profile|get_player_valuation|'
  r'get_player_replacements|get_cluster_summary',
);

/// Natural Spanish step title for a tool identifier (never prints snake_case).
String chatToolStepTitle(String? tool) =>
    _stepTitles[tool] ?? 'Consulta de datos del modelo';

/// Natural Spanish step description, stripped of any literal function names.
String chatToolStepSummary(String? tool, String? rawSummary) {
  final trimmed = rawSummary?.trim() ?? '';
  if (trimmed.isEmpty ||
      trimmed.contains('La herramienta') ||
      _literalToolPattern.hasMatch(trimmed)) {
    return _fallbackSummaries[tool] ??
        'Se consultaron los datos calculados por el modelo.';
  }
  return trimmed;
}
