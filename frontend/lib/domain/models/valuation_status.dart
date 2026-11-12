/// The model's single verdict on a player's price (DESIGN.md §2).
library;

/// The three valuation verdicts the pipeline publishes as `valuation_status`.
enum ValuationStatus {
  undervalued('undervalued'),
  fair('fair'),
  overvalued('overvalued');

  const ValuationStatus(this.apiValue);

  /// The value the backend sends and accepts as a filter.
  final String apiValue;

  /// The status for an API value, or `null` when it is missing or unknown.
  static ValuationStatus? fromApi(String? value) => switch (value) {
    'undervalued' => undervalued,
    'fair' => fair,
    'overvalued' => overvalued,
    _ => null,
  };
}
