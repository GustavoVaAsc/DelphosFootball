/// One item of `GET /players` (`PlayerSummary` in
/// `backend/src/delphos_backend/schemas/players.py`).
library;

import 'image_url_allowlist.dart';
import 'json_fields.dart';
import '../../domain/models/player_summary.dart';
import '../../domain/models/valuation_status.dart';

/// A player row as the backend lists it.
///
/// [fairValueEur] and [age] are optional and may be absent: the backend
/// does not send them yet, and a planned backend change adds them.
class PlayerSummaryDto {
  const PlayerSummaryDto({
    required this.playerId,
    required this.name,
    required this.position,
    this.subPosition,
    this.countryOfCitizenship,
    this.clubName,
    this.clubLogoUrl,
    this.imageUrl,
    this.marketValueEur,
    this.fairValueEur,
    this.age,
    this.valuationStatus,
    this.clusterId,
  });

  factory PlayerSummaryDto.fromJson(
    Map<String, Object?> json,
  ) => switch (json) {
    {'player_id': int playerId, 'name': String name, 'position': String p} =>
      PlayerSummaryDto(
        playerId: playerId,
        name: name,
        position: p,
        subPosition: optionalString(json, 'sub_position'),
        countryOfCitizenship: optionalString(json, 'country_of_citizenship'),
        clubName: optionalString(json, 'club_name'),
        clubLogoUrl: optionalString(json, 'club_logo_url'),
        imageUrl: optionalString(json, 'image_url'),
        marketValueEur: optionalDouble(json, 'market_value_eur'),
        fairValueEur: optionalDouble(json, 'fair_value_eur'),
        age: optionalDouble(json, 'age'),
        valuationStatus: optionalString(json, 'valuation_status'),
        clusterId: optionalInt(json, 'cluster_id'),
      ),
    _ => throw FormatException('Invalid player summary', json),
  };

  PlayerSummary toDomain() => PlayerSummary(
    id: playerId,
    name: name,
    position: position,
    subPosition: subPosition,
    country: countryOfCitizenship,
    clubName: clubName,
    clubLogoUrl: allowedImageUrl(clubLogoUrl),
    imageUrl: allowedImageUrl(imageUrl),
    marketValueEur: marketValueEur,
    fairValueEur: fairValueEur,
    age: age,
    valuationStatus: ValuationStatus.fromApi(valuationStatus),
    clusterId: clusterId,
  );

  final int playerId;
  final String name;
  final String position;
  final String? subPosition;
  final String? countryOfCitizenship;
  final String? clubName;
  final String? clubLogoUrl;
  final String? imageUrl;
  final double? marketValueEur;
  final double? fairValueEur;
  final double? age;
  final String? valuationStatus;
  final int? clusterId;
}
