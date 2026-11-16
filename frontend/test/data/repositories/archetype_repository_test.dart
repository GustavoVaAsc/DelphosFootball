// Tests for ArchetypeRepository against a fake backend: parsing the
// archetypes and totalling their players.
import 'package:delphos_frontend/data/repositories/archetype_repository.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/http_fakes.dart';

void main() {
  group('ArchetypeRepository', () {
    test('parses the archetypes and totals their players', () async {
      Map<String, Object?> cluster(int id, int count) => {
        'cluster_id': id,
        'name': 'English name',
        'player_count': count,
        'avg_market_value_eur': 12500000.0,
        'avg_minutes': 1800.5,
        'avg_goals': 4.2,
        'avg_assists': 3,
      };
      final repo = ArchetypeRepository(
        apiClient: fakeApi(
          (_) async => jsonResponse({
            'model_run_id': 'run_2025_v1',
            'season': 2025,
            'clusters': [cluster(0, 1500), cluster(1, 2200), cluster(2, 1822)],
          }),
        ),
      );
      final overview = await repo.getOverview();
      expect(overview.season, 2025);
      expect(overview.archetypes, hasLength(3));
      expect(overview.archetypes[1].avgAssists, 3.0);
      expect(overview.totalPlayers, 5522);
    });
  });
}
