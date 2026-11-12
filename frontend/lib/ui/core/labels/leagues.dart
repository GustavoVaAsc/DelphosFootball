/// Display names of the fourteen leagues in the modelling population, keyed
/// by Transfermarkt `league_id` (design preview `LEAGUE_NAMES`, identical to
/// `LEAGUE_LABELS` in `ml/src/delphos_domain/labels.py`).
library;

const Map<String, String> _leagues = {
  'GB1': 'Premier League',
  'ES1': 'LaLiga',
  'L1': 'Bundesliga',
  'IT1': 'Serie A',
  'FR1': 'Ligue 1',
  'PO1': 'Primeira Liga',
  'NL1': 'Eredivisie',
  'TR1': 'Süper Lig',
  'BE1': 'Pro League',
  'DK1': 'Superliga',
  'SC1': 'Premiership',
  'GR1': 'Super League',
  'UKR1': 'Premier Liga',
  'RU1': 'Premier Liga',
};

/// The league's display name, or `null` for an unknown id (the raw code is
/// never shown).
String? leagueLabel(String? leagueId) => _leagues[leagueId];
