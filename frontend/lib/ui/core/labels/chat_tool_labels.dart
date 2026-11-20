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

/// Text that reads as code, not as a sentence: braces, a JSON key (`"a":`),
/// a JSON array, or a snake_case identifier such as a tool name or an
/// argument key (every tool name is one).
final RegExp _technicalPattern = RegExp(
  r'[{}]|"[^"]*"\s*:|\[\s*["{]|\b[a-z]+(?:_[a-z0-9]+)+\b',
);

bool _readsAsCode(String text) => _technicalPattern.hasMatch(text);

/// Natural Spanish step title for a tool identifier (never prints snake_case).
String chatToolStepTitle(String? tool) =>
    _stepTitles[tool] ?? 'Consulta de datos del modelo';

/// The live description of a step ("Buscando delanteros infravalorados…"),
/// as the server wrote it, or the generic [chatToolStepTitle] when it is
/// missing or reads as code (a tool name, braces, argument keys).
String chatToolStepDescription(String? tool, String? rawDescription) {
  final trimmed = rawDescription?.trim() ?? '';
  if (trimmed.isEmpty || _readsAsCode(trimmed)) return chatToolStepTitle(tool);
  return trimmed;
}

/// Natural Spanish step summary, stripped of any literal function names,
/// braces and argument keys.
String chatToolStepSummary(String? tool, String? rawSummary) {
  final trimmed = rawSummary?.trim() ?? '';
  if (trimmed.isEmpty ||
      trimmed.contains('La herramienta') ||
      _readsAsCode(trimmed)) {
    return _fallbackSummaries[tool] ??
        'Se consultaron los datos calculados por el modelo.';
  }
  return trimmed;
}
