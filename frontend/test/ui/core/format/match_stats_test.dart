// Tests for the match-stat helpers: height "1,84 m", minutes, and starts
// above matches played printing as N/D (DESIGN.md §3).
import 'package:delphos_frontend/ui/core/format/match_stats.dart';
import 'package:flutter_test/flutter_test.dart';

const nbsp = '\u00A0';

void main() {
  group('formatHeight', () {
    test('prints metres with two decimals', () {
      expect(formatHeight(184), '1,84${nbsp}m');
      expect(formatHeight(180), '1,80${nbsp}m');
    });

    test('prints N/D for a missing or non-positive height', () {
      expect(formatHeight(null), 'N/D');
      expect(formatHeight(0), 'N/D');
    });
  });

  group('formatMinutes', () {
    test('groups thousands and adds the minute mark', () {
      expect(formatMinutes(4285), "4.285'");
    });

    test('prints a missing value as N/D without the minute mark', () {
      expect(formatMinutes(null), 'N/D');
    });
  });

  group('starts', () {
    test('are valid between zero and matches played', () {
      expect(validStarts(starts: 45, apps: 56), 45);
      expect(validStarts(starts: 56, apps: 56), 56);
      expect(validStarts(starts: 0, apps: 3), 0);
    });

    test('above matches played, negative or missing are unknown', () {
      expect(validStarts(starts: 20, apps: 15), isNull);
      expect(validStarts(starts: -1, apps: 15), isNull);
      expect(validStarts(starts: null, apps: 15), isNull);
      expect(validStarts(starts: 5, apps: null), isNull);
    });

    test('print beside matches played, or N/D when impossible', () {
      expect(formatAppsWithStarts(apps: 56, starts: 45), '56 (45)');
      expect(formatAppsWithStarts(apps: 15, starts: 20), '15 (N/D)');
      expect(formatAppsWithStarts(apps: null, starts: null), 'N/D (N/D)');
    });
  });
}
