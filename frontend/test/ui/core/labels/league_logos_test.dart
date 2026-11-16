// Tests for the league logo URL: derived from the id, only for known
// leagues, always on the allowlisted host.
import 'package:delphos_frontend/data/models/image_url_allowlist.dart';
import 'package:delphos_frontend/ui/core/labels/league_logos.dart';
import 'package:delphos_frontend/ui/core/labels/leagues.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('builds the lowercase Transfermarkt header logo URL', () {
    expect(
      leagueLogoUrl('GB1'),
      'https://tmssl.akamaized.net/images/logo/header/gb1.png',
    );
    expect(
      leagueLogoUrl('UKR1'),
      'https://tmssl.akamaized.net/images/logo/header/ukr1.png',
    );
  });

  test('all 14 known leagues have a URL that passes the allowlist', () {
    expect(knownLeagueIds, hasLength(14));
    for (final id in knownLeagueIds) {
      final url = leagueLogoUrl(id)!;
      expect(allowedImageUrl(url), url, reason: id);
      expect(url, endsWith('/${id.toLowerCase()}.png'), reason: id);
    }
  });

  test('an unknown or missing league has no logo', () {
    expect(leagueLogoUrl('XX9'), isNull);
    expect(leagueLogoUrl('../evil'), isNull);
    expect(leagueLogoUrl(null), isNull);
  });
}
