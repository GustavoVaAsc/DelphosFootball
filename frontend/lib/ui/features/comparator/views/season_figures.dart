/// A player's season figures as the comparator displays them (DESIGN.md
/// §4): counts rounded, age in whole years, starter and win shares in whole
/// percentage points, and `null` for a share the data does not support.
/// The comparison rules in `compare_rules.dart` work on these values, so
/// every delta is computed from what the table prints.
library;

import '../../../../domain/models/player_profile.dart';
import '../../../core/format/format.dart';
import '../../../core/labels/leagues.dart';

/// A player's season figures as the table displays them.
typedef SeasonFigures = ({
  String? league,
  int? age,
  int? minutes,
  int? goals,
  int? assists,
  int? starter,
  int? win,
});

/// The displayed figures of [profile], or `null` without a season row.
SeasonFigures? seasonFigures(PlayerProfile? profile) {
  final s = profile?.season;
  if (s == null) return null;
  int? points(double share) => switch (validShare(share)) {
    final value? => (value * 100).round(),
    null => null,
  };
  return (
    league: leagueLabel(s.leagueId),
    age: s.age.floor(),
    minutes: s.minutes.round(),
    goals: s.goals.round(),
    assists: s.assists.round(),
    starter: points(s.starterRatio),
    win: points(s.winRate),
  );
}
