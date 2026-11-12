// Backend-shaped JSON for the three dossier endpoints of one player:
// /players/{id}, /players/{id}/valuation and /players/{id}/replacements.
import 'player_fixtures.dart';

/// The JSON the backend would send for [path].
Map<String, Object?> dossierJsonFor(String path) {
  final segments = Uri.parse(path).pathSegments;
  final id = int.parse(segments[1]);
  return switch (segments.length) {
    2 => {
      ...profileJson(season: seasonJson()),
      'player_id': id,
      'name': 'Jugador $id',
    },
    _ when segments.last == 'valuation' => valuationJson(id),
    _ => replacementsJson(id),
  };
}

Map<String, Object?> valuationJson(
  int id, {
  String status = 'undervalued',
  bool rf = true,
  bool dt = true,
  double probability = 0.71,
}) => {
  'player_id': id,
  'name': 'Jugador $id',
  'model_run_id': 'run_test',
  'season': 2025,
  'market_value_eur': 60000000.0,
  'fair_value_eur': 155900000.0,
  'residual_log10': 0.41,
  'valuation_status': status,
  'is_undervalued': status == 'undervalued',
  'rf_undervalued_prob': probability,
  'dt_undervalued_pred': dt,
  'rf_undervalued_pred': rf,
};

Map<String, Object?> replacementsJson(
  int id, {
  int count = 3,
  String? shortfall,
  bool elite = true,
}) => {
  'target_player_id': id,
  'target_name': 'Jugador $id',
  'model_run_id': 'run_test',
  'season': 2025,
  'is_elite_asset': elite,
  'target_market_value_eur': 150000000.0,
  'qualifying_count': count,
  'shortfall_reason': shortfall,
  'replacements': [
    for (var rank = 1; rank <= count; rank++)
      {
        'rank': rank,
        'candidate_player_id': id * 10 + rank,
        'candidate_name': 'Candidato $rank',
        'position': 'Attack',
        'candidate_country_of_citizenship': 'Brazil',
        'candidate_club_id': 1,
        'candidate_club_name': 'Club con un nombre largo número $rank',
        'candidate_club_logo_url': null,
        'candidate_image_url': null,
        'similarity_score': 0.9 - rank / 100,
        'euclidean_distance': 0.4,
        'candidate_market_value_eur': 40000000.0,
        'cost_savings_eur': 110000000.0,
        'cost_ratio': 0.2667,
        'candidate_fair_value_eur': 45000000.0,
        'candidate_valuation_status': 'fair',
      },
  ],
};
