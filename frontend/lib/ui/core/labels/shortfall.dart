/// The sentence that explains why a player has fewer than three replacement
/// candidates, from the published `shortfall_reason` code (DESIGN.md §7).
/// Codes never reach the UI raw.
library;

import '../format/numbers.dart';

/// The shortfall sentence, or `null` when [qualifyingCount] is three or more.
String? describeShortfall({required int qualifyingCount, String? reason}) {
  if (qualifyingCount >= 3) return null;
  final players = formatCount(
    qualifyingCount,
    'jugador cumple',
    'jugadores cumplen',
  );
  return switch (reason) {
    'no_same_cluster_and_position_peer' =>
      'Ningún otro jugador comparte arquetipo y posición.',
    'no_peer_within_athletic_distance' =>
      'Ningún jugador del mismo arquetipo y posición está dentro de la '
          'distancia de similitud exigida.',
    'no_peer_below_cost_ceiling' =>
      'Ningún jugador similar cuesta al menos un 20% menos.',
    'no_non_overvalued_peer' =>
      'Los jugadores similares y más baratos están sobrevalorados.',
    'fewer_than_three_qualifying_peers' =>
      'Solo $players todos los criterios: mismo arquetipo y posición, '
          'similitud suficiente, ahorro mínimo del 20% y no sobrevalorado.',
    _ when qualifyingCount == 0 =>
      'Ningún jugador cumple los criterios de reemplazo.',
    _ => 'Solo $players los criterios de reemplazo.',
  };
}
