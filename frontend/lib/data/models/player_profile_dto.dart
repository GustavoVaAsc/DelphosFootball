/// The body of `GET /players/{id}` (`PlayerProfileResponse` in
/// `backend/src/delphos_backend/schemas/players.py`).
library;

import 'image_url_allowlist.dart';
import 'json_fields.dart';
import 'season_metrics_dto.dart';
import '../../domain/models/player_profile.dart';

/// A player's biography and active season, as the backend sends them.
class PlayerProfileDto {
  const PlayerProfileDto({
    required this.playerId,
    required this.name,
    required this.lastName,
    required this.dateOfBirth,
    required this.position,
    required this.url,
    this.firstName,
    this.countryOfCitizenship,
    this.subPosition,
    this.foot,
    this.heightInCm,
    this.clubName,
    this.clubLogoUrl,
    this.imageUrl,
    this.clusterId,
    this.activeSeason,
  });

  factory PlayerProfileDto.fromJson(
    Map<String, Object?> json,
  ) => switch (json) {
    {
      'player_id': int playerId,
      'name': String name,
      'last_name': String lastName,
      'date_of_birth': String dateOfBirth,
      'position': String position,
      'url': String url,
    } =>
      PlayerProfileDto(
        playerId: playerId,
        name: name,
        lastName: lastName,
        dateOfBirth: parseIsoDate('date_of_birth', dateOfBirth),
        position: position,
        url: url,
        firstName: optionalString(json, 'first_name'),
        countryOfCitizenship: optionalString(json, 'country_of_citizenship'),
        subPosition: optionalString(json, 'sub_position'),
        foot: optionalString(json, 'foot'),
        heightInCm: optionalInt(json, 'height_in_cm'),
        clubName: optionalString(json, 'club_name'),
        clubLogoUrl: optionalString(json, 'club_logo_url'),
        imageUrl: optionalString(json, 'image_url'),
        clusterId: optionalInt(json, 'cluster_id'),
        activeSeason: switch (json['active_season']) {
          null => null,
          final Map<String, Object?> season => SeasonMetricsDto.fromJson(
            season,
          ),
          final other => throw FormatException('Invalid active season', other),
        },
      ),
    _ => throw FormatException('Invalid player profile', json),
  };

  PlayerProfile toDomain() => PlayerProfile(
    id: playerId,
    name: name,
    lastName: lastName,
    dateOfBirth: dateOfBirth,
    position: position,
    transfermarktUrl: url,
    firstName: firstName,
    country: countryOfCitizenship,
    subPosition: subPosition,
    foot: foot,
    heightCm: heightInCm,
    clubName: clubName,
    clubLogoUrl: allowedImageUrl(clubLogoUrl),
    imageUrl: allowedImageUrl(imageUrl),
    clusterId: clusterId,
    season: activeSeason?.toDomain(),
  );

  final int playerId;
  final String name;
  final String lastName;
  final DateTime dateOfBirth;
  final String position;
  final String url;
  final String? firstName;
  final String? countryOfCitizenship;
  final String? subPosition;
  final String? foot;
  final int? heightInCm;
  final String? clubName;
  final String? clubLogoUrl;
  final String? imageUrl;
  final int? clusterId;
  final SeasonMetricsDto? activeSeason;
}
