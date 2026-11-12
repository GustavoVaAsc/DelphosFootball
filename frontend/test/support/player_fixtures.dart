// Backend-shaped JSON for player endpoints, modelled on Michael Olise's row
// in the design preview data.

Map<String, Object?> summaryJson({Map<String, Object?> extra = const {}}) => {
  'player_id': 566723,
  'name': 'Michael Olise',
  'first_name': 'Michael',
  'last_name': 'Olise',
  'position': 'Attack',
  'sub_position': 'Right Winger',
  'country_of_citizenship': 'France',
  'club_id': 27,
  'club_name': 'Bayern Munich',
  'club_logo_url': 'https://tmssl.akamaized.net/images/wappen/head/27.png',
  'market_value_eur': 150000000.00000003,
  'valuation_status': 'fair',
  'cluster_id': 0,
  'cluster_name': 'Attacking Creators & Scorers',
  'image_url': null,
  ...extra,
};

Map<String, Object?> listJson(List<Map<String, Object?>> items) => {
  'model_run_id': 'run_2025_v1',
  'items': items,
  'total': 5522,
  'page': 2,
  'page_size': 20,
  'total_pages': 277,
};

Map<String, Object?> seasonJson() => {
  'season': 2025,
  'as_of_date': '2026-05-27',
  'league_id': 'L1',
  'minutes': 4285.0,
  'apps': 56.0,
  'starts': 45.0,
  'goals': 25.0,
  'assists': 32.0,
  'yellow_cards': 12.0,
  'red_cards': 0.0,
  'starter_ratio': 0.8036,
  'win_rate': 0.8036,
  'clean_sheet_rate': 0.2857,
  'goals_conceded_per_match': 1.179,
  'league_position': 1.0,
  'age': 24.5,
};

Map<String, Object?> profileJson({Object? season}) => {
  'model_run_id': 'run_2025_v1',
  'player_id': 566723,
  'name': 'Michael Olise',
  'first_name': 'Michael',
  'last_name': 'Olise',
  'player_code': 'michael-olise',
  'country_of_citizenship': 'Türkiye',
  'date_of_birth': '2001-12-12',
  'position': 'Attack',
  'sub_position': 'Right Winger',
  'foot': 'left',
  'height_in_cm': 180,
  'club_id': 27,
  'club_name': 'Bayern Munich',
  'club_logo_url': null,
  'image_url': null,
  'url': 'https://www.transfermarkt.co.uk/michael-olise/profil/spieler/566723',
  'cluster_id': 0,
  'cluster_name': 'Attacking Creators & Scorers',
  'active_season': season,
};
