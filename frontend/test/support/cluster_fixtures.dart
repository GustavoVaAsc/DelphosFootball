// Backend-shaped JSON for GET /clusters: three archetypes with the live
// player counts (1.219, 503 and 3.800 of 5.522).

/// The /clusters answer.
Map<String, Object?> clustersJson() => {
  'model_run_id': 'run_test',
  'season': 2025,
  'as_of_date': '2026-06-05',
  'clusters': [
    for (final (id, count) in [(0, 1219), (1, 503), (2, 3800)])
      {
        'cluster_id': id,
        'name': 'English',
        'player_count': count,
        'avg_market_value_eur': 1.0,
        'avg_minutes': 1.0,
        'avg_goals': 1.0,
        'avg_assists': 1.0,
      },
  ],
};
