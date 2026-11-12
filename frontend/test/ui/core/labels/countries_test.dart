// Tests for the country table: Spanish names, flag codes, and that the
// bundled flag files match the table exactly (assets/flags/LICENSE.md).
import 'dart:io';

import 'package:delphos_frontend/ui/core/labels/countries.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('maps dataset spellings to Spanish names', () {
    expect(countryNameEs('Spain'), 'España');
    expect(countryNameEs('Korea, South'), 'Corea del Sur');
    expect(countryNameEs("Cote d'Ivoire"), 'Costa de Marfil');
    expect(countryNameEs('Türkiye'), 'Turquía');
    expect(countryNameEs('Turkey'), 'Turquía');
    expect(countryNameEs('Réunion'), 'Reunión');
    expect(countryNameEs('Neukaledonien'), 'Nueva Caledonia');
  });

  test('uses the home-nation flags for the UK football nations', () {
    expect(countryFlagCode('England'), 'gb-eng');
    expect(countryFlagCode('Scotland'), 'gb-sct');
    expect(countryFlagCode('Wales'), 'gb-wls');
    expect(countryFlagCode('Northern Ireland'), 'gb-nir');
  });

  test('shows no flag rather than a wrong one', () {
    expect(countryNameEs('Chinese Taipei'), 'China Taipéi');
    expect(countryFlagCode('Chinese Taipei'), isNull);
  });

  test('returns null for an unmapped or missing country', () {
    expect(countryNameEs('Atlantis'), isNull);
    expect(countryFlagCode(null), isNull);
  });

  test('every flag code has a bundled file and every file has a code', () {
    final codes = {
      for (final country in mappedCountries) ?countryFlagCode(country),
    };
    final files = Directory('assets/flags')
        .listSync()
        .whereType<File>()
        .map((file) => file.uri.pathSegments.last)
        .where((name) => name.endsWith('.png'))
        .map((name) => name.substring(0, name.length - 4))
        .toSet();
    expect(files, codes);
  });
}
