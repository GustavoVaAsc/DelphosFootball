// Tests for route id parsing: one to ten ASCII digits, at most 2147483647.
import 'package:delphos_frontend/routing/route_params.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('accepts one to ten digits up to the 32-bit maximum', () {
    expect(parseRouteId('0'), 0);
    expect(parseRouteId('566723'), 566723);
    expect(parseRouteId('2147483647'), 2147483647);
  });

  test('rejects anything else', () {
    for (final value in [
      null,
      '',
      '2147483648',
      '99999999999',
      '-1',
      '+5',
      ' 5',
      '5 ',
      '0x1F',
      '1e3',
      '1.0',
      '١٢',
    ]) {
      expect(parseRouteId(value), isNull, reason: '$value');
    }
  });
}
