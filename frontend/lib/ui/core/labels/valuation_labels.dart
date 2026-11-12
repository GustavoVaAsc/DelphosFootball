/// The Spanish verdict for each valuation status, identical in pills,
/// filters, comparator and report text (DESIGN.md §3 "Vocabulary").
library;

import '../../../domain/models/valuation_status.dart';

/// "Infravalorado", "En precio" or "Sobrevalorado".
String valuationStatusLabel(ValuationStatus status) => switch (status) {
  ValuationStatus.undervalued => 'Infravalorado',
  ValuationStatus.fair => 'En precio',
  ValuationStatus.overvalued => 'Sobrevalorado',
};
