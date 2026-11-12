// Tests for the es-ES number helpers: grouping, signs, percentages, shares
// and multiples (DESIGN.md §3 "Number format" and "No impossible figures").
import 'package:delphos_frontend/ui/core/format/numbers.dart';
import 'package:flutter_test/flutter_test.dart';

const minus = '\u2212';

void main() {
  group('formatNumber', () {
    test('groups thousands with a dot, four digits included', () {
      expect(formatNumber(5522), '5.522');
      expect(formatNumber(1234567), '1.234.567');
      expect(formatNumber(999), '999');
    });

    test('uses a decimal comma', () {
      expect(formatNumber(1.179, decimals: 2), '1,18');
      expect(formatNumber(1234.5, decimals: 1), '1.234,5');
    });

    test('prints negatives with U+2212, never a hyphen', () {
      expect(formatNumber(-5522), '${minus}5.522');
    });

    test('drops the sign when the value rounds to zero', () {
      expect(formatNumber(-0.004, decimals: 2), '0,00');
    });

    test('prints N/D for a missing or non-finite value', () {
      expect(formatNumber(null), 'N/D');
      expect(formatNumber(double.nan), 'N/D');
      expect(formatNumber(double.infinity), 'N/D');
    });
  });

  group('formatSignedNumber', () {
    test('adds a plus to positives and U+2212 to negatives', () {
      expect(formatSignedNumber(12), '+12');
      expect(formatSignedNumber(-3), '${minus}3');
    });

    test('prints a value that rounds to zero as ±0', () {
      expect(formatSignedNumber(0), '±0');
      expect(formatSignedNumber(-0.2), '±0');
    });
  });

  group('formatCount', () {
    test('picks the singular only for exactly one', () {
      expect(formatCount(1, 'jugador', 'jugadores'), '1 jugador');
      expect(formatCount(2, 'jugador', 'jugadores'), '2 jugadores');
      expect(formatCount(5522, 'jugador', 'jugadores'), '5.522 jugadores');
    });
  });

  group('formatPct', () {
    test('prints whole percentages by default', () {
      expect(formatPct(0.2361), '24%');
      expect(formatPct(-0.27), '${minus}27%');
    });

    test('prints exactly ±1 as ±100%', () {
      expect(formatPct(1), '100%');
      expect(formatPct(-1), '${minus}100%');
    });

    test('gives a near-100 value one decimal instead of 100%', () {
      expect(formatPct(0.995), '99,5%');
      expect(formatPct(-0.995), '${minus}99,5%');
      expect(formatPct(1.004), '100,4%');
    });

    test('clamps a value that still rounds to 100 to ±99,9 or ±100,1', () {
      expect(formatPct(0.9996), '99,9%');
      expect(formatPct(-0.9996), '${minus}99,9%');
      expect(formatPct(1.0003), '100,1%');
      expect(formatPct(-1.0003), '${minus}100,1%');
    });

    test('prints N/D for a missing ratio', () {
      expect(formatPct(null), 'N/D');
    });
  });

  group('formatSignedPct', () {
    test('adds a plus only when the printed value is not zero', () {
      expect(formatSignedPct(0.12), '+12%');
      expect(formatSignedPct(0.001), '0%');
      expect(formatSignedPct(-0.12), '${minus}12%');
    });
  });

  group('shares', () {
    test('accept values inside 0..1, bounds included', () {
      expect(validShare(0), 0);
      expect(validShare(1), 1);
      expect(formatShare(0.8036), '80%');
      expect(formatShare(1), '100%');
    });

    test('print N/D outside 0..1 instead of repeating bad data', () {
      expect(validShare(2.47), isNull);
      expect(validShare(-0.01), isNull);
      expect(formatShare(2.47), 'N/D');
      expect(formatShare(-0.01), 'N/D');
      expect(formatShare(null), 'N/D');
    });
  });

  group('formatMultiple', () {
    test('prints one decimal with an x', () {
      expect(formatMultiple(1.27), '1,3x');
      expect(formatMultiple(0.05), '0,1x');
    });

    test('prints a positive ratio under 0,05 as <0,1x, never 0,0x', () {
      expect(formatMultiple(0.04), '<0,1x');
      expect(formatMultiple(0.0001), '<0,1x');
    });

    test('prints zero as 0,0x and missing as N/D', () {
      expect(formatMultiple(0), '0,0x');
      expect(formatMultiple(null), 'N/D');
    });
  });
}
