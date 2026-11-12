// Tests for the euro helpers: "€150,0 M" for millions, "€153 mil" for
// thousands, U+2212 for negatives (DESIGN.md §3 "Number format").
import 'package:delphos_frontend/ui/core/format/money.dart';
import 'package:flutter_test/flutter_test.dart';

const minus = '\u2212';
const nbsp = '\u00A0';

void main() {
  group('formatEur', () {
    test('prints millions with one decimal and M', () {
      expect(formatEur(150000000.00000003), '€150,0${nbsp}M');
      expect(formatEur(190799569.95), '€190,8${nbsp}M');
    });

    test('prints thousands rounded with mil', () {
      expect(formatEur(153000), '€153${nbsp}mil');
      expect(formatEur(1000), '€1${nbsp}mil');
    });

    test('switches to millions where thousands would print 1.000 mil', () {
      expect(formatEur(999499), '€999${nbsp}mil');
      expect(formatEur(999500), '€1,0${nbsp}M');
    });

    test('switches to thousands where euros would print 1.000', () {
      expect(formatEur(999.49), '€999');
      expect(formatEur(999.5), '€1${nbsp}mil');
      expect(formatEur(999.99), '€1${nbsp}mil');
    });

    test('prints values under a thousand as plain euros', () {
      expect(formatEur(950), '€950');
      expect(formatEur(0), '€0');
    });

    test('puts U+2212 before the euro sign for negatives', () {
      expect(formatEur(-5000000), '$minus€5,0${nbsp}M');
    });

    test('prints N/D for a missing value', () {
      expect(formatEur(null), 'N/D');
    });
  });

  group('formatSignedEur', () {
    test('adds a plus to positives only', () {
      expect(formatSignedEur(30000000), '+€30,0${nbsp}M');
      expect(formatSignedEur(-30000000), '$minus€30,0${nbsp}M');
      expect(formatSignedEur(0), '€0');
    });
  });
}
