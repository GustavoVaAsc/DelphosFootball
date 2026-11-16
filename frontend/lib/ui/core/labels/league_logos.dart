/// The Transfermarkt logo URL of a league, built from its `league_id`
/// (`GB1` becomes `.../images/logo/header/gb1.png`).
///
/// The dataset carries no league logo URL, so the URL is derived here, for
/// the leagues of `labels/leagues.dart` only: a raw or poisoned id never
/// reaches a URL. The result still goes through `allowedImageUrl`, so a
/// future change to the template cannot leave the allowlisted hosts
/// (ADR-026; `tmssl.akamaized.net` is already in `img-src` and `connect-src`).
library;

import '../../../data/models/image_url_allowlist.dart';
import 'leagues.dart';

/// The logo URL for [leagueId], or `null` for an unknown league.
String? leagueLogoUrl(String? leagueId) => leagueLabel(leagueId) == null
    ? null
    : allowedImageUrl(
        'https://tmssl.akamaized.net/images/logo/header/'
        '${leagueId!.toLowerCase()}.png',
      );
