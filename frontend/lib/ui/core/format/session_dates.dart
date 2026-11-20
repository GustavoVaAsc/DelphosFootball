/// The date of a saved conversation in the chat's "Conversaciones" list:
/// "Hoy 14:05" and "Ayer 09:30" for the last two days, then "5 nov 2026".
library;

import 'dates.dart';

/// [date] in the reader's local time, relative to [now] (also local time
/// after `toLocal`). Days are calendar days, not 24-hour spans.
String formatSessionDate(DateTime date, {required DateTime now}) {
  final local = date.toLocal();
  final today = DateTime(now.year, now.month, now.day);
  final day = DateTime(local.year, local.month, local.day);
  final days = today.difference(day).inDays;
  final time =
      '${local.hour.toString().padLeft(2, '0')}:'
      '${local.minute.toString().padLeft(2, '0')}';
  return switch (days) {
    0 => 'Hoy $time',
    1 => 'Ayer $time',
    _ => formatDate(local),
  };
}
