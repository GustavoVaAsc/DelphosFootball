/// The market table's footer line (DESIGN.md §4: "18 de 5.522 jugadores").
library;

import '../../../core/format/numbers.dart';

/// "18 de 5.522 jugadores" when the list fits on one page (or "18
/// jugadores" before the dataset total is known); "Mostrando 1 a 50 de
/// 1.219 jugadores" when it spans pages.
String tableFooterText({
  required int total,
  required int page,
  required int pageSize,
  int? datasetTotal,
}) {
  if (total > pageSize) {
    final from = (page - 1) * pageSize + 1;
    final to = (page * pageSize).clamp(from, total);
    return 'Mostrando ${formatNumber(from)} a ${formatNumber(to)} '
        'de ${formatNumber(total)} jugadores';
  }
  if (datasetTotal == null) {
    return formatCount(total, 'jugador', 'jugadores');
  }
  return '${formatNumber(total)} de ${formatNumber(datasetTotal)} jugadores';
}
