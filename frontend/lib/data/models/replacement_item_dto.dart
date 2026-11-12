/// One candidate of `GET /players/{id}/replacements` (`ReplacementItem` in
/// `backend/src/delphos_backend/schemas/replacements.py`).
library;

import 'image_url_allowlist.dart';
import 'json_fields.dart';
import '../../domain/models/replacement.dart';
import '../../domain/models/valuation_status.dart';

/// A ranked replacement candidate, as the backend sends it.
class ReplacementItemDto {
  const ReplacementItemDto({
    required this.rank,
    required this.candidatePlayerId,
    required this.candidateName,
    required this.position,
    required this.similarityScore,
    required this.candidateMarketValueEur,
    required this.costSavingsEur,
    required this.costRatio,
    required this.candidateFairValueEur,
    required this.candidateValuationStatus,
    this.candidateCountryOfCitizenship,
    this.candidateClubName,
    this.candidateClubLogoUrl,
    this.candidateImageUrl,
  });

  factory ReplacementItemDto.fromJson(Map<String, Object?> json) =>
      switch (json) {
        {
          'rank': int rank,
          'candidate_player_id': int candidatePlayerId,
          'candidate_name': String candidateName,
          'position': String position,
          'similarity_score': num similarityScore,
          'candidate_market_value_eur': num candidateMarketValueEur,
          'cost_savings_eur': num costSavingsEur,
          'cost_ratio': num costRatio,
          'candidate_fair_value_eur': num candidateFairValueEur,
          'candidate_valuation_status': String candidateValuationStatus,
        } =>
          ReplacementItemDto(
            rank: rank,
            candidatePlayerId: candidatePlayerId,
            candidateName: candidateName,
            position: position,
            similarityScore: similarityScore.toDouble(),
            candidateMarketValueEur: candidateMarketValueEur.toDouble(),
            costSavingsEur: costSavingsEur.toDouble(),
            costRatio: costRatio.toDouble(),
            candidateFairValueEur: candidateFairValueEur.toDouble(),
            candidateValuationStatus: candidateValuationStatus,
            candidateCountryOfCitizenship: optionalString(
              json,
              'candidate_country_of_citizenship',
            ),
            candidateClubName: optionalString(json, 'candidate_club_name'),
            candidateClubLogoUrl: optionalString(
              json,
              'candidate_club_logo_url',
            ),
            candidateImageUrl: optionalString(json, 'candidate_image_url'),
          ),
        _ => throw FormatException('Invalid replacement candidate', json),
      };

  Replacement toDomain() => Replacement(
    rank: rank,
    playerId: candidatePlayerId,
    name: candidateName,
    position: position,
    similarity: similarityScore,
    marketValueEur: candidateMarketValueEur,
    savingsEur: costSavingsEur,
    costRatio: costRatio,
    fairValueEur: candidateFairValueEur,
    status: ValuationStatus.fromApi(candidateValuationStatus),
    country: candidateCountryOfCitizenship,
    clubName: candidateClubName,
    clubLogoUrl: allowedImageUrl(candidateClubLogoUrl),
    imageUrl: allowedImageUrl(candidateImageUrl),
  );

  final int rank;
  final int candidatePlayerId;
  final String candidateName;
  final String position;
  final double similarityScore;
  final double candidateMarketValueEur;
  final double costSavingsEur;
  final double costRatio;
  final double candidateFairValueEur;
  final String candidateValuationStatus;
  final String? candidateCountryOfCitizenship;
  final String? candidateClubName;
  final String? candidateClubLogoUrl;
  final String? candidateImageUrl;
}
