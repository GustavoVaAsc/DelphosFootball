// Tests for DatasetViewModel: the total, season and data date from
// /clusters, and an empty result when the request fails.
import 'package:delphos_frontend/data/repositories/archetype_repository.dart';
import 'package:delphos_frontend/ui/core/view_models/dataset_view_model.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../../support/http_fakes.dart';

Map<String, Object?> cluster(int id, int count) => {
  'cluster_id': id,
  'name': 'English',
  'player_count': count,
  'avg_market_value_eur': 1.0,
  'avg_minutes': 1.0,
  'avg_goals': 1.0,
  'avg_assists': 1.0,
};

void main() {
  test('sums the archetypes and reads the season and data date', () async {
    final vm = DatasetViewModel(
      archetypes: ArchetypeRepository(
        apiClient: fakeApi(
          (_) async => jsonResponse({
            'model_run_id': 'r',
            'season': 2025,
            'as_of_date': '2026-06-05',
            'clusters': [cluster(0, 1219), cluster(1, 503), cluster(2, 3800)],
          }),
        ),
      ),
    );
    await vm.load();
    expect(vm.totalPlayers, 5522);
    expect(vm.overview!.season, 2025);
    expect(vm.overview!.asOfDate, DateTime(2026, 6, 5));
  });

  test('works without as_of_date and reports a failure', () async {
    final ok = DatasetViewModel(
      archetypes: ArchetypeRepository(
        apiClient: fakeApi(
          (_) async => jsonResponse({
            'model_run_id': 'r',
            'season': 2025,
            'clusters': [cluster(0, 10)],
          }),
        ),
      ),
    );
    await ok.load();
    expect(ok.overview!.asOfDate, isNull);
    final down = DatasetViewModel(
      archetypes: ArchetypeRepository(
        apiClient: fakeApi((_) async => problemResponse(503, 'x', 'y')),
      ),
    );
    await down.load();
    expect(down.failed, isTrue);
    expect(down.totalPlayers, isNull);
  });
}
