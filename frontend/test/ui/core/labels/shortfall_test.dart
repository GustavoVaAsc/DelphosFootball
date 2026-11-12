// Tests for the replacement shortfall messages (DESIGN.md §7): codes never
// reach the UI raw, and three or more candidates need no message.
import 'package:delphos_frontend/ui/core/labels/shortfall.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('three or more candidates have no shortfall', () {
    expect(describeShortfall(qualifyingCount: 3), isNull);
    expect(
      describeShortfall(
        qualifyingCount: 3,
        reason: 'no_peer_below_cost_ceiling',
      ),
      isNull,
    );
  });

  test('each known code has its own sentence', () {
    const expected = {
      'no_same_cluster_and_position_peer':
          'Ningún otro jugador comparte arquetipo y posición.',
      'no_peer_within_athletic_distance':
          'Ningún jugador del mismo arquetipo y posición está dentro de la '
          'distancia de similitud exigida.',
      'no_peer_below_cost_ceiling':
          'Ningún jugador similar cuesta al menos un 20% menos.',
      'no_non_overvalued_peer':
          'Los jugadores similares y más baratos están sobrevalorados.',
    };
    expected.forEach(
      (code, text) =>
          expect(describeShortfall(qualifyingCount: 0, reason: code), text),
    );
  });

  test('fewer than three qualifying peers states the count', () {
    const tail =
        'todos los criterios: mismo arquetipo y posición, similitud '
        'suficiente, ahorro mínimo del 20% y no sobrevalorado.';
    expect(
      describeShortfall(
        qualifyingCount: 2,
        reason: 'fewer_than_three_qualifying_peers',
      ),
      'Solo 2 jugadores cumplen $tail',
    );
    expect(
      describeShortfall(
        qualifyingCount: 1,
        reason: 'fewer_than_three_qualifying_peers',
      ),
      'Solo 1 jugador cumple $tail',
    );
  });

  test('an unknown or missing code gets a generic sentence', () {
    expect(
      describeShortfall(qualifyingCount: 2, reason: 'some_new_code'),
      'Solo 2 jugadores cumplen los criterios de reemplazo.',
    );
    expect(
      describeShortfall(qualifyingCount: 0),
      'Ningún jugador cumple los criterios de reemplazo.',
    );
  });
}
