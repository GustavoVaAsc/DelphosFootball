/// Referenced-player payload attached to a PitIA message (`ChatReferencedPlayer`
/// in `backend/src/delphos_backend/schemas/chat.py`).
library;

import '../../domain/models/chat_referenced_player.dart';
import '../../domain/models/valuation_status.dart';
import 'image_url_allowlist.dart';
import 'json_fields.dart';

/// One player card hydrated outside the LLM context window.
class ChatReferencedPlayerDto {
  const ChatReferencedPlayerDto({
    required this.playerId,
    required this.name,
    this.position,
    this.subPosition,
    this.country,
    this.clubName,
    this.clubLogoUrl,
    this.leagueId,
    this.imageUrl,
    this.marketValueEur,
    this.fairValueEur,
    this.valuationStatus,
  });

  factory ChatReferencedPlayerDto.fromJson(Map<String, Object?> json) =>
      switch (json) {
        {'player_id': int playerId, 'name': String name} =>
          ChatReferencedPlayerDto(
            playerId: playerId,
            name: name,
            position: optionalString(json, 'position'),
            subPosition: optionalString(json, 'sub_position'),
            country: optionalString(json, 'country'),
            clubName: optionalString(json, 'club_name'),
            clubLogoUrl: optionalString(json, 'club_logo_url'),
            leagueId: optionalString(json, 'league_id'),
            imageUrl: optionalString(json, 'image_url'),
            marketValueEur: optionalDouble(json, 'market_value_eur'),
            fairValueEur: optionalDouble(json, 'fair_value_eur'),
            valuationStatus: optionalString(json, 'valuation_status'),
          ),
        _ => throw FormatException('Invalid chat referenced player', json),
      };

  /// Parses an optional JSON list, skipping malformed items without failing the
  /// live turn or session restore.
  static List<ChatReferencedPlayer> parseList(Object? raw) {
    if (raw is! List<Object?>) return const [];
    final players = <ChatReferencedPlayer>[];
    for (final item in raw) {
      if (item is! Map<Object?, Object?>) continue;
      try {
        final json = <String, Object?>{
          for (final entry in item.entries)
            if (entry.key is String) entry.key as String: entry.value,
        };
        players.add(ChatReferencedPlayerDto.fromJson(json).toDomain());
      } on FormatException {
        // Skip malformed entries so the assistant prose still renders.
      }
    }
    return players;
  }

  ChatReferencedPlayer toDomain() => ChatReferencedPlayer(
    id: playerId,
    name: name,
    position: position,
    subPosition: subPosition,
    country: country,
    clubName: clubName,
    clubLogoUrl: allowedImageUrl(clubLogoUrl),
    leagueId: leagueId,
    imageUrl: allowedImageUrl(imageUrl),
    marketValueEur: marketValueEur,
    fairValueEur: fairValueEur,
    valuationStatus: ValuationStatus.fromApi(valuationStatus),
  );

  final int playerId;
  final String name;
  final String? position;
  final String? subPosition;
  final String? country;
  final String? clubName;
  final String? clubLogoUrl;
  final String? leagueId;
  final String? imageUrl;
  final double? marketValueEur;
  final double? fairValueEur;
  final String? valuationStatus;
}
