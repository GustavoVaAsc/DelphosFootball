// Tests that PlayerRepository passes portrait and crest URLs through the
// image allowlist (ADR-026) when it maps the player list.
import 'package:delphos_frontend/data/repositories/player_repository.dart';
import 'package:delphos_frontend/domain/models/player_query.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/http_fakes.dart';
import '../../support/player_fixtures.dart';

void main() {
  test('keeps allowed image URLs and drops the rest', () async {
    final kept = summaryJson();
    final dropped = summaryJson(
      extra: {
        'club_logo_url': 'http://tmssl.akamaized.net/27.png',
        'image_url': 'https://evil.example/p.jpg',
      },
    );
    final repo = PlayerRepository(
      apiClient: fakeApi((_) async => jsonResponse(listJson([kept, dropped]))),
    );
    final players = (await repo.listPlayers(const PlayerQuery())).players;
    expect(
      players[0].clubLogoUrl,
      'https://tmssl.akamaized.net/images/wappen/head/27.png',
    );
    expect(players[1].clubLogoUrl, isNull);
    expect(players[1].imageUrl, isNull);
  });
}
