// Tests for PlayerRepository's single-player reads against a fake backend:
// profile with and without a season, valuation, and replacements.
import 'package:delphos_frontend/data/repositories/player_repository.dart';
import 'package:delphos_frontend/domain/models/valuation_status.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import '../../support/http_fakes.dart';
import '../../support/player_fixtures.dart';

void main() {
  group('getProfile', () {
    test('parses the biography and the season, decoding UTF-8', () async {
      final log = <http.Request>[];
      final repo = PlayerRepository(
        apiClient: fakeApi(
          (_) async => jsonResponse(
            profileJson(season: seasonJson()),
            contentType: 'application/json',
          ),
          log: log,
        ),
      );
      final profile = await repo.getProfile(566723);
      expect(log.single.url.path, '/players/566723');
      expect(profile.country, 'Türkiye');
      expect(profile.dateOfBirth, DateTime(2001, 12, 12));
      expect(profile.heightCm, 180);
      expect(profile.foot, 'left');
      final season = profile.season!;
      expect(season.asOfDate, DateTime(2026, 5, 27));
      expect(season.apps, 56);
      expect(season.starts, 45);
      expect(season.goalsConcededPerMatch, 1.179);
      expect(season.leaguePosition, 1);
    });

    test('keeps a player without season statistics', () async {
      final repo = PlayerRepository(
        apiClient: fakeApi((_) async => jsonResponse(profileJson())),
      );
      expect((await repo.getProfile(566723)).season, isNull);
    });
  });

  group('getValuation', () {
    Map<String, Object?> valuationJson(String status) => {
      'player_id': 566723,
      'name': 'Michael Olise',
      'model_run_id': 'run_2025_v1',
      'season': 2025,
      'market_value_eur': 150000000.0,
      'fair_value_eur': 190799569.95,
      'residual_log10': 0.1045,
      'valuation_status': status,
      'is_undervalued': false,
      'rf_undervalued_prob': 0.2361,
      'dt_undervalued_pred': false,
      'rf_undervalued_pred': false,
    };

    test('parses the verdict and the classifier check', () async {
      final repo = PlayerRepository(
        apiClient: fakeApi((_) async => jsonResponse(valuationJson('fair'))),
      );
      final valuation = await repo.getValuation(566723);
      expect(valuation.status, ValuationStatus.fair);
      expect(valuation.fairValueEur, 190799569.95);
      expect(valuation.rfUndervaluedProb, 0.2361);
      expect(valuation.dtUndervaluedPred, isFalse);
    });

    test('refuses an unknown verdict', () async {
      final repo = PlayerRepository(
        apiClient: fakeApi((_) async => jsonResponse(valuationJson('cheap'))),
      );
      expect(repo.getValuation(1), throwsA(isA<FormatException>()));
    });
  });

  group('getReplacements', () {
    test('parses candidates and the shortfall reason', () async {
      final repo = PlayerRepository(
        apiClient: fakeApi(
          (_) async => jsonResponse({
            'target_player_id': 1,
            'target_name': 'Rayan',
            'model_run_id': 'run_2025_v1',
            'season': 2025,
            'is_elite_asset': true,
            'target_market_value_eur': 40000000.0,
            'qualifying_count': 1,
            'shortfall_reason': 'fewer_than_three_qualifying_peers',
            'replacements': [
              {
                'rank': 1,
                'candidate_player_id': 2,
                'candidate_name': 'Candidate',
                'position': 'Attack',
                'candidate_country_of_citizenship': 'Brazil',
                'candidate_club_id': null,
                'candidate_club_name': null,
                'candidate_club_logo_url': null,
                'candidate_image_url': 'javascript:alert(1)',
                'similarity_score': 0.91,
                'euclidean_distance': 0.4,
                'candidate_market_value_eur': 12000000.0,
                'cost_savings_eur': 28000000.0,
                'cost_ratio': 0.3,
                'candidate_fair_value_eur': 15000000.0,
                'candidate_valuation_status': 'undervalued',
              },
            ],
          }),
        ),
      );
      final set = await repo.getReplacements(1);
      expect(set.qualifyingCount, 1);
      expect(set.shortfallReason, 'fewer_than_three_qualifying_peers');
      expect(set.isEliteAsset, isTrue);
      final candidate = set.candidates.single;
      expect(candidate.savingsEur, 28000000);
      expect(candidate.similarity, 0.91);
      expect(candidate.status, ValuationStatus.undervalued);
      expect(candidate.country, 'Brazil');
      expect(candidate.imageUrl, isNull);
    });
  });
}
