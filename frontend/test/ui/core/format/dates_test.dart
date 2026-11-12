// Tests for the date helpers: "27 may 2026", seasons as "2025/26" and whole
// ages from a birth date (DESIGN.md §3 and §7 "no-season").
import 'package:delphos_frontend/ui/core/format/dates.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('formatDate', () {
    test('prints day, short Spanish month and year', () {
      expect(formatDate(DateTime(2026, 5, 27)), '27 may 2026');
      expect(formatDate(DateTime(2026, 6, 5)), '5 jun 2026');
      expect(formatDate(DateTime(2025, 1, 1)), '1 ene 2025');
      expect(formatDate(DateTime(2025, 12, 31)), '31 dic 2025');
    });

    test('prints a date-time in local time', () {
      final utc = DateTime.utc(2026, 1, 1, 0, 30);
      final local = utc.toLocal();
      const months = [
        'ene', 'feb', 'mar', 'abr', 'may', 'jun', //
        'jul', 'ago', 'sep', 'oct', 'nov', 'dic',
      ];
      expect(
        formatDate(utc),
        '${local.day} ${months[local.month - 1]} ${local.year}',
      );
    });

    test('prints N/D for a missing date', () {
      expect(formatDate(null), 'N/D');
    });
  });

  group('formatSeason', () {
    test('prints the start year and the two-digit end year', () {
      expect(formatSeason(2025), '2025/26');
      expect(formatSeason(2009), '2009/10');
      expect(formatSeason(2099), '2099/00');
    });
  });

  group('ageOn', () {
    test('counts whole years, before and after the birthday', () {
      final birth = DateTime(2001, 12, 12);
      expect(ageOn(birth, DateTime(2026, 6, 5)), 24);
      expect(ageOn(birth, DateTime(2026, 12, 12)), 25);
      expect(ageOn(birth, DateTime(2026, 12, 11)), 24);
    });

    test('returns null when either date is missing', () {
      expect(ageOn(null, DateTime(2026, 6, 5)), isNull);
      expect(ageOn(DateTime(2001, 12, 12), null), isNull);
    });
  });
}
