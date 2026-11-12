/// The `active_season` object of `GET /players/{id}` (`PlayerSeasonMetrics`
/// in `backend/src/delphos_backend/schemas/players.py`).
library;

import 'json_fields.dart';
import '../../domain/models/season_stats.dart';

/// A player's active-season figures, as the backend sends them.
class SeasonMetricsDto {
  const SeasonMetricsDto({
    required this.season,
    required this.asOfDate,
    required this.leagueId,
    required this.minutes,
    required this.apps,
    required this.starts,
    required this.goals,
    required this.assists,
    required this.yellowCards,
    required this.redCards,
    required this.starterRatio,
    required this.winRate,
    required this.cleanSheetRate,
    required this.goalsConcededPerMatch,
    required this.age,
    this.leaguePosition,
  });

  factory SeasonMetricsDto.fromJson(Map<String, Object?> json) =>
      switch (json) {
        {
          'season': int season,
          'as_of_date': String asOfDate,
          'league_id': String leagueId,
          'minutes': num minutes,
          'apps': num apps,
          'starts': num starts,
          'goals': num goals,
          'assists': num assists,
          'yellow_cards': num yellowCards,
          'red_cards': num redCards,
          'starter_ratio': num starterRatio,
          'win_rate': num winRate,
          'clean_sheet_rate': num cleanSheetRate,
          'goals_conceded_per_match': num goalsConcededPerMatch,
          'age': num age,
        } =>
          SeasonMetricsDto(
            season: season,
            asOfDate: parseIsoDate('as_of_date', asOfDate),
            leagueId: leagueId,
            minutes: minutes.toDouble(),
            apps: apps.toDouble(),
            starts: starts.toDouble(),
            goals: goals.toDouble(),
            assists: assists.toDouble(),
            yellowCards: yellowCards.toDouble(),
            redCards: redCards.toDouble(),
            starterRatio: starterRatio.toDouble(),
            winRate: winRate.toDouble(),
            cleanSheetRate: cleanSheetRate.toDouble(),
            goalsConcededPerMatch: goalsConcededPerMatch.toDouble(),
            age: age.toDouble(),
            leaguePosition: optionalDouble(json, 'league_position'),
          ),
        _ => throw FormatException('Invalid season metrics', json),
      };

  SeasonStats toDomain() => SeasonStats(
    season: season,
    asOfDate: asOfDate,
    leagueId: leagueId,
    minutes: minutes,
    apps: apps,
    starts: starts,
    goals: goals,
    assists: assists,
    yellowCards: yellowCards,
    redCards: redCards,
    starterRatio: starterRatio,
    winRate: winRate,
    cleanSheetRate: cleanSheetRate,
    goalsConcededPerMatch: goalsConcededPerMatch,
    age: age,
    leaguePosition: leaguePosition,
  );

  final int season;
  final DateTime asOfDate;
  final String leagueId;
  final double minutes;
  final double apps;
  final double starts;
  final double goals;
  final double assists;
  final double yellowCards;
  final double redCards;
  final double starterRatio;
  final double winRate;
  final double cleanSheetRate;
  final double goalsConcededPerMatch;
  final double age;
  final double? leaguePosition;
}
