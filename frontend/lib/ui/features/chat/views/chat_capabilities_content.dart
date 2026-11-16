/// The copy of the capabilities pop-up: what the assistant does, and the
/// example prompts.
library;

/// Title and description of each capability.
const List<(String, String)> chatCapabilities = [
  (
    'Búsquedas de jugadores',
    'Localiza jugadores por nombre, club, país, posición, diagnóstico de valoración o arquetipo táctico.',
  ),
  (
    'Valoración y acuerdo entre modelos',
    'Consulta precio de mercado, valor estimado y el acuerdo entre Random Forest y el árbol de decisión.',
  ),
  (
    'Comparaciones y reemplazos Moneyball',
    'Contrasta estadísticas de la temporada 2025/26, arquetipos tácticos y candidatos de reemplazo más económicos.',
  ),
  (
    'Cada consulta a la vista',
    'Muestra los pasos que sigue sobre los datos del modelo.',
  ),
];

/// Label and prompt of each quick example.
const List<(String, String)> chatSamplePrompts = [
  (
    'Extremos infravalorados sub-24',
    'Busca extremos infravalorados menores de 24 años.',
  ),
  (
    'Compara a Harry Kane con reemplazos',
    'Compara la valoración y el rendimiento de Harry Kane con sus reemplazos.',
  ),
  (
    'Resume los 3 arquetipos tácticos',
    'Resume los tres arquetipos tácticos calculados en la plantilla.',
  ),
];
