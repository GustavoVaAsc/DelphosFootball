/// The filters and page of a player list request.
library;

import 'valuation_status.dart';

/// What to list: every filter is optional, pages are 1-based, and a page
/// holds at most [maxPageSize] players (the backend's limit).
class PlayerQuery {
  const PlayerQuery({
    this.name,
    this.position,
    this.valuationStatus,
    this.clusterId,
    this.page = 1,
    this.pageSize = defaultPageSize,
  });

  static const int defaultPageSize = 20;
  static const int maxPageSize = 100;

  /// A name substring.
  final String? name;

  /// The dataset's English position key ("Attack", "Midfield", "Defender").
  final String? position;
  final ValuationStatus? valuationStatus;
  final int? clusterId;
  final int page;
  final int pageSize;
}
