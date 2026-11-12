// Tests for the market table's footer line: the range when the list has
// more than one page, the count against the dataset when it fits on one.
import 'package:delphos_frontend/ui/features/explorer/views/table_footer_text.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('a list that fits on one page counts against the dataset', () {
    expect(
      tableFooterText(total: 18, page: 1, pageSize: 50, datasetTotal: 5522),
      '18 de 5.522 jugadores',
    );
    expect(
      tableFooterText(total: 1, page: 1, pageSize: 50, datasetTotal: 5522),
      '1 de 5.522 jugadores',
    );
  });

  test('without the dataset total it states the count alone', () {
    expect(tableFooterText(total: 18, page: 1, pageSize: 50), '18 jugadores');
    expect(tableFooterText(total: 1, page: 1, pageSize: 50), '1 jugador');
  });

  test('a paged list states the range and the filtered total', () {
    expect(
      tableFooterText(total: 1219, page: 1, pageSize: 50, datasetTotal: 5522),
      'Mostrando 1 a 50 de 1.219 jugadores',
    );
    expect(
      tableFooterText(total: 1219, page: 25, pageSize: 50, datasetTotal: 5522),
      'Mostrando 1.201 a 1.219 de 1.219 jugadores',
    );
  });
}
