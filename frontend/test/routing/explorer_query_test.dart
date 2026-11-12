// Tests for the explorer's URL state: Spanish query parameters parse into
// filters, bad values are dropped, and the round trip is stable (ADR-024).
import 'package:delphos_frontend/domain/models/valuation_status.dart';
import 'package:delphos_frontend/routing/explorer_query.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('parses every parameter', () {
    final query = ExplorerQuery.fromQueryParameters({
      'estado': 'infravalorado',
      'posicion': 'mediocampo',
      'arquetipo': '2',
      'q': ' Olise ',
      'pagina': '3',
      'jugador': '566723',
    });
    expect(query.status, ValuationStatus.undervalued);
    expect(query.position, 'Midfield');
    expect(query.clusterId, 2);
    expect(query.search, 'Olise');
    expect(query.page, 3);
    expect(query.playerId, 566723);
    expect(query.isDossierOpen, isTrue);
  });

  test('drops unknown or malformed values instead of failing', () {
    final query = ExplorerQuery.fromQueryParameters({
      'estado': 'barato',
      'posicion': 'portero',
      'arquetipo': '-1',
      'q': '   ',
      'pagina': '0',
      'jugador': 'abc',
    });
    expect(query.status, isNull);
    expect(query.position, isNull);
    expect(query.clusterId, isNull);
    expect(query.search, isNull);
    expect(query.page, 1);
    expect(query.playerId, isNull);
    expect(query.isDossierOpen, isFalse);
  });

  test('drops a search above 100 characters and oversized ids', () {
    final query = ExplorerQuery.fromQueryParameters({
      'q': 'a' * 101,
      'arquetipo': '99999999999',
      'pagina': '2147483648',
      'jugador': '0x10',
    });
    expect(query.search, isNull);
    expect(query.clusterId, isNull);
    expect(query.page, 1);
    expect(query.playerId, isNull);
    final atLimit = ExplorerQuery.fromQueryParameters({
      'q': 'b' * 100,
      'jugador': '2147483647',
    });
    expect(atLimit.search, hasLength(100));
    expect(atLimit.playerId, 2147483647);
  });

  test('writes only non-default values, in Spanish', () {
    const query = ExplorerQuery(
      status: ValuationStatus.fair,
      position: 'Defender',
      playerId: 9,
    );
    expect(query.toQueryParameters(), {
      'estado': 'en-precio',
      'posicion': 'defensa',
      'jugador': '9',
    });
    expect(const ExplorerQuery().toQueryParameters(), isEmpty);
  });

  test('round-trips through the URL', () {
    const query = ExplorerQuery(
      status: ValuationStatus.overvalued,
      position: 'Attack',
      clusterId: 0,
      search: 'Pedri',
      page: 4,
      playerId: 12,
    );
    final parsed = ExplorerQuery.fromQueryParameters(query.toQueryParameters());
    expect(parsed.toQueryParameters(), query.toQueryParameters());
  });

  test('becomes the repository query with the same filters', () {
    const query = ExplorerQuery(
      status: ValuationStatus.undervalued,
      position: 'Attack',
      clusterId: 1,
      search: 'Saka',
      page: 2,
    );
    final playerQuery = query.toPlayerQuery();
    expect(playerQuery.valuationStatus, ValuationStatus.undervalued);
    expect(playerQuery.position, 'Attack');
    expect(playerQuery.clusterId, 1);
    expect(playerQuery.name, 'Saka');
    expect(playerQuery.page, 2);
  });
}
