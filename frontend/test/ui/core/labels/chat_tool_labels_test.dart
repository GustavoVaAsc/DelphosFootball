// Rules of the assistant's step labels: a server description or summary is
// shown as written unless it reads as code (a tool name, braces, JSON or an
// argument key); then the generic Spanish label takes its place.
import 'package:delphos_frontend/ui/core/labels/chat_tool_labels.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('chatToolStepDescription', () {
    test('keeps a natural sentence from the server', () {
      expect(
        chatToolStepDescription(
          'search_players',
          'Buscando delanteros infravalorados ordenados por infravaloración',
        ),
        'Buscando delanteros infravalorados ordenados por infravaloración',
      );
    });

    test('falls back to the generic title when missing or blank', () {
      const title = 'Búsqueda de jugadores en el mercado';
      expect(chatToolStepDescription('search_players', null), title);
      expect(chatToolStepDescription('search_players', '  '), title);
    });

    test('never lets a tool name, braces or an argument key through', () {
      const title = 'Consulta de perfil y estadísticas';
      for (final raw in [
        'Ejecutando get_player_profile',
        'Buscando {"position": "Attack"}',
        'Buscando jugadores con sub_position=Right Winger',
        'Consultando ["a", "b"]',
        'Consultando }',
      ]) {
        expect(chatToolStepDescription('get_player_profile', raw), title);
      }
    });
  });

  group('chatToolStepSummary', () {
    test('replaces code-looking summaries with the fallback sentence', () {
      const fallback = 'Se consultó el catálogo de jugadores del modelo.';
      for (final raw in [
        '{"total": 2}',
        'Resultado: {ok}',
        'Se usó min_age en la búsqueda.',
        'La herramienta devolvió 2 jugadores.',
      ]) {
        expect(chatToolStepSummary('search_players', raw), fallback);
      }
    });

    test('keeps a natural summary', () {
      expect(
        chatToolStepSummary('search_players', 'Se encontraron 2 jugadores.'),
        'Se encontraron 2 jugadores.',
      );
    });
  });
}
