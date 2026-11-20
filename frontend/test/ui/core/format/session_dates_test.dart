// Tests for the saved-conversation date: "Hoy 14:05", "Ayer 09:30", then
// the short date.
import 'package:delphos_frontend/ui/core/format/session_dates.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final now = DateTime(2026, 11, 19, 15, 30);

  test('today prints the time', () {
    final afternoon = DateTime(2026, 11, 19, 14, 5);
    final midnight = DateTime(2026, 11, 19);
    expect(formatSessionDate(afternoon, now: now), 'Hoy 14:05');
    expect(formatSessionDate(midnight, now: now), 'Hoy 00:00');
  });

  test('yesterday is a calendar day, not 24 hours', () {
    final lateNight = DateTime(2026, 11, 18, 23, 59);
    final morning = DateTime(2026, 11, 18, 9, 30);
    expect(formatSessionDate(lateNight, now: now), 'Ayer 23:59');
    expect(
      formatSessionDate(morning, now: DateTime(2026, 11, 19, 0, 5)),
      'Ayer 09:30',
    );
  });

  test('older days print the short date', () {
    final twoDaysAgo = DateTime(2026, 11, 17, 23, 59);
    final lastYear = DateTime(2025, 1, 2, 8);
    expect(formatSessionDate(twoDaysAgo, now: now), '17 nov 2026');
    expect(formatSessionDate(lastYear, now: now), '2 ene 2025');
  });

  test('a UTC date-time prints in local time', () {
    final utc = DateTime.utc(2026, 11, 19, 12, 0);
    final local = utc.toLocal();
    final time =
        '${local.hour.toString().padLeft(2, '0')}:'
        '${local.minute.toString().padLeft(2, '0')}';
    final sameDay = DateTime(local.year, local.month, local.day, 23, 0);
    expect(formatSessionDate(utc, now: sameDay), 'Hoy $time');
  });
}
